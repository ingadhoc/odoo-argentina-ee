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
