# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestGeneralLedgerCsvExport(AccountTestInvoicingCommon):
    """The CSV export of the General Ledger, against the branch gate of the buttons."""

    PARENT_VAT = "30111111118"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["res.company"].create({"name": "Casa Matriz", "vat": cls.PARENT_VAT})
        cls.env["res.company"].create(
            {"name": "Sucursal mismo CUIT", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT}
        )

    def test_the_general_ledger_csv_export_is_not_gated_by_the_branch_check(self):
        """It was the one export button of the report without ``branch_allowed``.

        So the same report, with the same selection, exported to XLSX and refused to export
        to CSV with an error about the company selector — and what the file holds is what
        the user ticked, which is a complete answer whatever else the tree holds.
        """
        report = self.env.ref("account_reports.general_ledger_report")
        report = report.with_context(allowed_company_ids=self.parent.ids)

        options = report.get_options({"selected_variant_id": report.id})

        exports = {button["name"]: button for button in options["buttons"] if button.get("file_export_type")}
        self.assertIn("CSV", exports, "the General Ledger carries the CSV export this test is about")
        self.assertTrue(exports["CSV"]["branch_allowed"])
        self.assertFalse(exports["CSV"].get("error_action"))
        self.assertFalse(exports["XLSX"].get("error_action"), "and it agrees with the native one next to it")
