from base64 import b64encode
from os import path

from odoo.addons.l10n_ar.tests.common import TestArCommon
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
            file_data = b64encode(f.read())

        # Create attachment and get wizard through journal method
        result = self.company_data["default_journal_purchase"].import_bills_from_xls(
            [
                self.env["ir.attachment"].create(
                    {
                        "name": filename,
                        "datas": file_data,
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
            attachment = self.env["ir.attachment"].create({"name": "Exento.xlsx", "datas": b64encode(f.read())})

        action = journal.create_document_from_attachment(attachment_ids=[attachment.id])
        self.assertEqual(action.get("res_model"), "afip.import.wizard", "El importador debería dispararse para Exento")
        wizard = self.env["afip.import.wizard"].browse(action["res_id"])

        # Pre-creamos los proveedores para evitar la consulta externa a AFIP que
        # dispara _get_partner_by_vat al crear un partner CUIT nuevo.
        for line in wizard.line_ids:
            if not self.env["res.partner"].search([("vat", "=", line.partner_vat)], limit=1):
                id_type = self.env["l10n_latam.identification.type"].search(
                    [("name", "ilike", line.partner_identification_type)], limit=1
                )
                self.env["res.partner"].create(
                    {
                        "name": line.partner_name,
                        "vat": line.partner_vat,
                        "l10n_latam_identification_type_id": id_type.id,
                        "company_type": "company",
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
            partner = self.env["res.partner"].search([("vat", "=", line.partner_vat)], limit=1)
            partner_by_vat = line._get_partner_by_vat()
            if partner:
                self.assertEqual(partner, partner_by_vat, f"Partner VAT should match for line {line}")
            else:
                # If partner doesn't exist, it should be created
                self.assertTrue(partner_by_vat, f"Partner should be created for line {line}")
                self.assertEqual(
                    partner_by_vat.vat, line.partner_vat, f"Created partner VAT should match for line {line}"
                )
                self.assertEqual(
                    partner_by_vat.l10n_latam_identification_type_id.name,
                    line.partner_identification_type,
                    f"Identification type should match for line {line}",
                )
