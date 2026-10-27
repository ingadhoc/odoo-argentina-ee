from os import path

from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.addons.l10n_ar.tools.partner_identifiers import AR_CUIT_AFIP_CODE
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAfipImportWizard(TestArCommon):
    def _get_wizard_from_file(self, filename):
        """Helper to create and return wizard from file
        Args:
            filename (str): Name of file in fixtures folder
        Returns:
            afip.import.wizard: Created wizard record
        """
        with open(path.join(path.dirname(__file__), "fixtures", filename), "rb") as f:
            file_data = f.read()

        # Create attachment and get wizard through journal method
        result = self.company_data["default_journal_purchase"].import_bills_from_xls(
            [
                self.env["ir.attachment"].create(
                    {
                        "name": filename,
                        "raw": file_data,
                    }
                )
            ]
        )

        return self.env["afip.import.wizard"].browse(result["res_id"])

    def test_invoice_document_type(self):
        """Test correct assignment of document types based on file data"""
        # Load test file containing different invoice types
        wizard = self._get_wizard_from_file("invoice_type_test.xlsx")

        # Process the file
        view_return = wizard.action_confirm()
        invoice_ids = view_return["domain"][0][2]
        # Verify number of lines matches expected documents
        self.assertEqual(len(invoice_ids), 6, "Should find 6 invoices")

        # Expected document types in order
        expected_types = [
            "1",  # Factura A
            "2",  # Nota de Débito A
            "3",  # Nota de Crédito A
            "6",  # Factura B
            "11",  # Factura C
            "15",  # Recibo C
        ]

        # Verify each line has correct type
        for idx, expected_code in enumerate(expected_types):
            invoice = self.env["account.move"].browse(invoice_ids)[idx]

            self.assertEqual(invoice.l10n_latam_document_type_id.code, expected_code)

    def test_exento_import_without_vat(self):
        """Un Sujeto Exento importa comprobantes B/C sin ningún impuesto de IVA.

        La base de test trae una company demo (AR) Exento (code 4). Importamos a
        través de create_document_from_attachment para cubrir además el ruteo del
        importador para responsabilidades distintas de RI.
        """
        company = self.env["res.company"].search([("l10n_ar_afip_responsibility_type_id.code", "=", "4")], limit=1)
        self.assertTrue(company, "No hay company Exento (code 4) en la base de test")
        self.env.user.company_ids = [(4, company.id)]
        self.env.user.company_id = company

        journal = self.env["account.journal"].create(
            {"name": "Test Purchase Exento", "code": "TPEX", "type": "purchase", "company_id": company.id}
        )

        with open(path.join(path.dirname(__file__), "fixtures", "Exento.xlsx"), "rb") as f:
            attachment = self.env["ir.attachment"].create({"name": "Exento.xlsx", "raw": f.read()})

        action = journal.create_document_from_attachment(attachment_ids=[attachment.id])
        self.assertEqual(action.get("res_model"), "afip.import.wizard", "El importador debería dispararse para Exento")
        wizard = self.env["afip.import.wizard"].browse(action["res_id"])

        # Pre-creamos los proveedores para evitar la consulta externa a AFIP que
        # dispara _get_partner_by_vat al crear un partner CUIT nuevo.
        for line in wizard.line_ids:
            if not self.env["res.partner"].search([("vat", "=", line.partner_vat)], limit=1):
                self.env["res.partner"].create(
                    {
                        "name": line.partner_name,
                        "vat": line.partner_vat,
                        "country_id": self.env.ref("base.ar").id,
                    }
                )

        expected_total = sum(wizard.line_ids.mapped("amount_total"))
        view_return = wizard.action_confirm()
        moves = self.env["account.move"].browse(view_return["domain"][0][2])

        self.assertEqual(len(moves), 24, "Deberían crearse las 24 facturas del archivo")

        for move in moves:
            iva_taxes = move.invoice_line_ids.tax_ids.filtered(lambda t: t.tax_group_id.l10n_ar_vat_afip_code)
            self.assertFalse(iva_taxes, f"Un exento no debe llevar impuesto de IVA (factura {move.name})")

        # El total importado debe conservarse (neto sin IVA + Otros Tributos).
        self.assertAlmostEqual(sum(moves.mapped("amount_total")), expected_total, places=2)

    def test_partner_creation_and_search(self):
        """Test correct creation and search of partners based on identification"""
        # Load test file containing partner data
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")

        # Process the file
        for line in wizard.line_ids:
            partner = line._find_partner()
            partner_by_vat = line._get_partner_by_vat()
            identifier_key = line._get_identifier_key()
            if partner:
                self.assertEqual(partner, partner_by_vat, f"Partner VAT should match for line {line}")
            elif identifier_key and identifier_key != "AR_CUIT":
                # Un documento de persona vive en los identificadores adicionales, no en el CUIT.
                self.assertEqual(
                    (partner_by_vat.additional_identifiers or {}).get(identifier_key),
                    line.partner_vat,
                    f"Identification type should match for line {line}",
                )
                self.assertFalse(partner_by_vat.vat, f"A personal document is not a CUIT for line {line}")
            else:
                self.assertEqual(
                    partner_by_vat.vat, line.partner_vat, f"Created partner VAT should match for line {line}"
                )
                self.assertEqual(
                    partner_by_vat.l10n_ar_afip_code,
                    AR_CUIT_AFIP_CODE,
                    f"Identification type should match for line {line}",
                )

    def test_identifier_key_from_arca_name(self):
        """El tipo que escribe ARCA se resuelve a la clave del identificador de 20."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]

        casos = {
            "CUIT": "AR_CUIT",
            "DNI": "AR_DNI",
            "CUIL": "AR_CUIL",
            "Pasaporte": "PASSPORT",
            "LC": "AR_LC",
            # Lo que ARCA no llena (la columna del receptor en un listado de compras)
            # llega como texto y no tiene que resolver a nada.
            "nan": None,
            "": None,
        }
        for nombre, esperado in casos.items():
            line.partner_identification_type = nombre
            self.assertEqual(line._get_identifier_key(), esperado, f"tipo {nombre!r}")

    def test_partner_with_passport_is_not_argentinian(self):
        """Un pasaporte no es un CUIT: va a los identificadores y no marca el país."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "Pasaporte"
        line.partner_vat = "XZ9087654"
        line.partner_name = "Proveedor del exterior"

        partner = line._get_partner_by_vat()

        self.assertEqual((partner.additional_identifiers or {}).get("PASSPORT"), "XZ9087654")
        self.assertFalse(partner.vat, "El pasaporte no va al campo del CUIT")
        self.assertNotEqual(partner.country_id, self.env.ref("base.ar"))

    def test_unknown_identification_type_does_not_set_country(self):
        """Sin tipo reconocible el número va a `vat`, como en 19.0, y sin país."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "nan"
        line.partner_vat = "99999999999"
        line.partner_name = "Tipo desconocido"

        partner = line._get_partner_by_vat()

        self.assertEqual(partner.vat, "99999999999")
        self.assertFalse(partner.country_id, "No se inventa el país del proveedor")

    def test_existing_partner_without_cuit_is_reused(self):
        """Un documento de persona ya cargado se reusa en vez de duplicar el contacto."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "DNI"
        line.partner_vat = "30123456"

        primero = line._get_partner_by_vat()
        self.assertTrue(primero)
        segundo = line._get_partner_by_vat()

        self.assertEqual(primero, segundo, "El segundo pase tiene que encontrar al primero")
        self.assertEqual(line._find_partner(), primero)

    def test_exists_matches_by_partner_without_cuit(self):
        """`exists` reconoce la factura de un proveedor sin CUIT, que no se busca por `vat`."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "DNI"
        line.partner_vat = "27345678"
        partner = line._get_partner_by_vat()

        line._compute_exists()
        self.assertFalse(line.exists, "Todavía no hay factura de ese proveedor")

        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "journal_id": wizard.journal_id.id,
                "company_id": wizard.company_id.id,
                "invoice_date": line.date_invoice,
                "l10n_latam_document_number": line.invoice_number,
            }
        )
        # El módulo busca por `display_name`, que en un borrador todavía no trae el
        # número del comprobante.
        move.name = line.invoice_number
        self.assertIn(line.invoice_number, move.display_name)

        line._compute_exists()
        self.assertTrue(line.exists, "La factura ya está: no se vuelve a importar")
