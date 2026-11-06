from os import path

from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.addons.l10n_ar.tools.partner_identifiers import AR_CUIT_AFIP_CODE
from odoo.addons.l10n_ar_import_bill.models.account_journal import clean_document_number
from odoo.exceptions import UserError
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
            "2",  # Debit Note A
            "3",  # Credit Note A
            "6",  # Factura B
            "11",  # Factura C
            "15",  # Recibo C
        ]

        # Verify each line has correct type
        for idx, expected_code in enumerate(expected_types):
            invoice = self.env["account.move"].browse(invoice_ids)[idx]

            self.assertEqual(invoice.l10n_latam_document_type_id.code, expected_code)

    def test_exento_import_without_vat(self):
        """A VAT-exempt company imports B/C documents with no VAT tax at all.

        The test database ships a demo AR company that is exempt (code 4). The import
        goes through create_document_from_attachment so it also covers the routing of
        the importer for responsibilities other than VAT-registered.
        """
        company = self.env["res.company"].search([("l10n_ar_afip_responsibility_type_id.code", "=", "4")], limit=1)
        self.assertTrue(company, "No exempt company (code 4) in the test database")
        self.env.user.company_ids = [(4, company.id)]
        self.env.user.company_id = company

        journal = self.env["account.journal"].create(
            {"name": "Test Purchase Exento", "code": "TPEX", "type": "purchase", "company_id": company.id}
        )

        with open(path.join(path.dirname(__file__), "fixtures", "Exento.xlsx"), "rb") as f:
            attachment = self.env["ir.attachment"].create({"name": "Exento.xlsx", "raw": f.read()})

        action = journal.create_document_from_attachment(attachment_ids=[attachment.id])
        self.assertEqual(
            action.get("res_model"), "afip.import.wizard", "The importer must trigger for an exempt company"
        )
        wizard = self.env["afip.import.wizard"].browse(action["res_id"])

        # The suppliers are created up front to avoid the external AFIP lookup that
        # _get_partner_by_vat triggers when it creates a new CUIT partner.
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

        self.assertEqual(len(moves), 24, "The 24 invoices of the file must be created")

        for move in moves:
            iva_taxes = move.invoice_line_ids.tax_ids.filtered(lambda t: t.tax_group_id.l10n_ar_vat_afip_code)
            self.assertFalse(iva_taxes, f"An exempt company carries no VAT tax (invoice {move.name})")

        # The imported total has to be preserved (net without VAT + other taxes).
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
                # A personal document lives in the additional identifiers, not in the CUIT.
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
        """The type ARCA writes resolves to the identifier key of 20.0."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]

        casos = {
            "CUIT": "AR_CUIT",
            "DNI": "AR_DNI",
            "CUIL": "AR_CUIL",
            "Pasaporte": "PASSPORT",
            "LC": "AR_LC",
            # What ARCA leaves empty (the receiver column of a purchases listing)
            # arrives as text and must resolve to nothing.
            "nan": None,
            "": None,
        }
        for nombre, esperado in casos.items():
            line.partner_identification_type = nombre
            self.assertEqual(line._get_identifier_key(), esperado, f"tipo {nombre!r}")

    def test_partner_with_passport_is_not_argentinian(self):
        """A passport is not a CUIT: it goes to the identifiers and sets no country."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "Pasaporte"
        line.partner_vat = "XZ9087654"
        line.partner_name = "Proveedor del exterior"

        partner = line._get_partner_by_vat()

        self.assertEqual((partner.additional_identifiers or {}).get("PASSPORT"), "XZ9087654")
        self.assertFalse(partner.vat, "A passport does not go to the CUIT field")
        self.assertNotEqual(partner.country_id, self.env.ref("base.ar"))

    def test_unknown_identification_type_does_not_set_country(self):
        """With no recognizable type the number goes to `vat`, like in 19.0, and with no country."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "nan"
        line.partner_vat = "99999999999"
        line.partner_name = "Tipo desconocido"

        partner = line._get_partner_by_vat()

        self.assertEqual(partner.vat, "99999999999")
        self.assertFalse(partner.country_id, "The country of the supplier is not made up")

    def test_existing_partner_without_cuit_is_reused(self):
        """A personal document already on file is reused instead of duplicating the contact."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "DNI"
        line.partner_vat = "30123456"

        primero = line._get_partner_by_vat()
        self.assertTrue(primero)
        segundo = line._get_partner_by_vat()

        self.assertEqual(primero, segundo, "The second pass has to find the first one")
        self.assertEqual(line._find_partner(), primero)

    def test_exists_matches_by_partner_without_cuit(self):
        """`exists` recognizes the invoice of a supplier with no CUIT, not searchable by `vat`."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "DNI"
        line.partner_vat = "27345678"
        partner = line._get_partner_by_vat()

        line._compute_exists()
        self.assertFalse(line.exists, "There is no invoice of that supplier yet")

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
        # The module searches `display_name`, which on a draft does not carry the
        # document number yet.
        move.name = line.invoice_number
        self.assertIn(line.invoice_number, move.display_name)

        line._compute_exists()
        self.assertTrue(line.exists, "The invoice is already in: it is not imported again")

    def test_dotted_document_is_found_again(self):
        """20.0 compacts what it stores, so the number as ARCA writes it still finds it."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "DNI"
        line.partner_vat = "30.123.456"
        line.partner_name = "Proveedor con DNI con puntos"

        primero = line._get_partner_by_vat()

        self.assertEqual((primero.additional_identifiers or {}).get("AR_DNI"), "30123456")
        self.assertEqual(line._find_partner(), primero, "The dotted document has to find it")
        self.assertEqual(line._get_partner_by_vat(), primero, "The contact is not duplicated")

    def test_dashed_cuit_is_found_again(self):
        """Same with the CUIT: it is stored compacted and the line brings it with dashes."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "CUIT"
        line.partner_vat = "20-11111111-2"
        line.partner_name = "Proveedor con CUIT con guiones"

        primero = line._get_partner_by_vat()

        self.assertEqual(primero.vat, "20111111112")
        self.assertEqual(line._find_partner(), primero, "The dashed CUIT has to find it")
        self.assertEqual(line._get_partner_by_vat(), primero, "The contact is not duplicated")

    def test_invalid_document_does_not_stop_the_import(self):
        """A document 20.0 does not accept cannot bring down the whole listing."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "DNI"
        line.partner_vat = "123"
        line.partner_name = "Documento invalido"

        partner = line._get_partner_by_vat()

        self.assertEqual(partner.vat, "123", "The number is stored like in 19.0")
        self.assertFalse(partner.additional_identifiers)
        self.assertFalse(partner.country_id, "With no country Odoo does not validate it")
        self.assertEqual(line._get_partner_by_vat(), partner, "The contact is not duplicated")

    def test_exists_matches_a_duplicated_contact(self):
        """An invoice already imported is recognized even on the duplicated contact."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "CUIT"
        line.partner_vat = "20-11111111-2"

        primero = line._get_partner_by_vat()
        duplicado = self.env["res.partner"].create(
            {"name": "Duplicado", "vat": "20111111112", "country_id": self.env.ref("base.ar").id}
        )
        self.assertNotEqual(primero, duplicado)

        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": duplicado.id,
                "journal_id": wizard.journal_id.id,
                "company_id": wizard.company_id.id,
                "invoice_date": line.date_invoice,
                "l10n_latam_document_number": line.invoice_number,
            }
        )
        move.name = line.invoice_number

        line._compute_exists()
        self.assertTrue(line.exists, "The invoice of the duplicated contact counts too")

    def test_document_number_survives_what_the_spreadsheet_holds(self):
        """A passport, an empty cell or a float tail must not abort the whole listing."""
        clean = clean_document_number

        self.assertEqual(clean(20111111112), "20111111112")
        self.assertEqual(clean(20111111112.0), "20111111112", "Pandas reads a number as a float")
        self.assertEqual(clean("20111111112.0"), "20111111112")
        self.assertEqual(clean("XZ9087654"), "XZ9087654", "A passport is text, not a number")
        self.assertEqual(clean(" 30123456 "), "30123456")
        self.assertEqual(clean(float("nan")), "", "An empty cell is a NaN")
        self.assertEqual(clean(None), "")

    def test_line_without_document_reuses_the_contact(self):
        """With no document the name is all there is: it must not create one per import."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = ""
        line.partner_vat = ""
        line.partner_name = "Supplier with no document"

        primero = line._get_partner_by_vat()

        self.assertEqual(primero.name, "Supplier with no document")
        self.assertEqual(line._get_partner_by_vat(), primero, "The second pass has to find it")

    def test_the_name_match_ignores_case(self):
        """ARCA writes the name in upper case; the contact on file rarely does."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        existente = self.env["res.partner"].create({"name": "Proveedor Ejemplo"})
        line = wizard.line_ids[0]
        line.partner_identification_type = ""
        line.partner_vat = ""
        line.partner_name = "PROVEEDOR EJEMPLO"

        self.assertEqual(line._get_partner_by_vat(), existente, "The contact on file has to be found")

    def test_the_name_match_only_reaches_contacts_with_no_document(self):
        """A supplier with a CUIT is not the contact of a line that carries no document."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        con_cuit = self.env["res.partner"].create(
            {"name": "Homonimo SA", "vat": "20111111112", "country_id": self.env.ref("base.ar").id}
        )
        line = wizard.line_ids[0]
        line.partner_identification_type = ""
        line.partner_vat = ""
        line.partner_name = "Homonimo SA"

        encontrado = line._get_partner_by_vat()

        self.assertNotEqual(encontrado, con_cuit, "A contact with a document is not reached by name")
        self.assertFalse(encontrado.vat)

    def test_a_line_without_document_nor_name_is_reported(self):
        """A nameless contact helps nobody: the line is named and the import stops."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = ""
        line.partner_vat = ""
        line.partner_name = ""

        with self.assertRaises(UserError):
            line._get_partner_by_vat()

    def test_a_credit_note_naming_the_invoice_is_not_the_invoice(self):
        """`display_name` carries the reference, and a credit note names what it cancels."""
        wizard = self._get_wizard_from_file("invoice_partner_test.xlsx")
        line = wizard.line_ids[0]
        line.partner_identification_type = "CUIT"
        line.partner_vat = "20-11111111-2"
        line.invoice_number = "00005-00000999"
        partner = line._get_partner_by_vat()

        self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "partner_id": partner.id,
                "journal_id": wizard.journal_id.id,
                "company_id": wizard.company_id.id,
                "invoice_date": line.date_invoice,
                "ref": "Credit note for invoice 00005-00000999",
            }
        )

        line._compute_exists()
        self.assertFalse(line.exists, "Invoice 00005-00000999 is not imported yet")

    def test_every_dropped_spreadsheet_is_imported(self):
        """Dropping several listings at once must not silently keep only the first."""
        journal = self.company_data["default_journal_purchase"]
        with open(path.join(path.dirname(__file__), "fixtures", "invoice_partner_test.xlsx"), "rb") as f:
            contenido = f.read()
        attachments = self.env["ir.attachment"].create(
            [
                {"name": "uno.xlsx", "raw": contenido},
                {"name": "dos.xlsx", "raw": contenido},
            ]
        )

        action = journal.import_bills_from_xls(attachments)
        wizard = self.env["afip.import.wizard"].browse(action["res_id"])

        una_sola = self._get_wizard_from_file("invoice_partner_test.xlsx")
        self.assertEqual(
            len(wizard.line_ids),
            2 * len(una_sola.line_ids),
            "The two dropped files have to end up in the same wizard",
        )
