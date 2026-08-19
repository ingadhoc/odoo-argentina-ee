# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestLegalEntityReports(AccountTestInvoicingCommon):
    """The reporting side of "which companies are the same legal entity".

    The criterion itself lives in ``account_ux`` and the bridge to Enterprise in this
    module's ``res_company.py``; what is checked here is what does *not* come for free
    with that bridge:

    * that any report says something when it is run with only part of the legal
      entity, which is the case the native code does not cover —
      ``_get_branches_with_same_vat(accessible_only=True)`` silently drops the
      companies that are not ticked in the company selector;
    * that the export buttons stop asking for the whole tree and ask for exactly the
      group that is the same legal entity.

    Scenario, all under the same root: a parent company with a Tax ID, a branch
    declaring the same one (same legal entity) and a third one with a Tax ID of its own
    (a different legal entity, which is why the whole tree cannot be selected without
    dirtying the report).
    """

    PARENT_VAT = "30111111118"
    OTHER_VAT = "30999999995"
    MISSING_WARNING = "account_accountant_ux.warning_missing_legal_entity_companies"
    SETTLEMENT_TITLE = "Settlement of the tests"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("account.generic_tax_report")
        cls.parent = cls.env["res.company"].create({"name": "Casa Matriz", "vat": cls.PARENT_VAT})
        cls.same_entity = cls.env["res.company"].create(
            {"name": "Sucursal mismo CUIT", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT}
        )
        cls.other_entity = cls.env["res.company"].create(
            {"name": "Sucursal otro CUIT", "parent_id": cls.parent.id, "vat": cls.OTHER_VAT}
        )
        # The button gate is only observable on a button that does not declare
        # ``branch_allowed``, and every native one (PDF, XLSX, Returns) is born with it.
        # This module's settlement button is one of those the gate does govern, so the
        # tests get one of their own instead of depending on whichever other module
        # installed on the database happens to add one.
        cls.report.write({"allow_settlement": True, "settlement_title": cls.SETTLEMENT_TITLE})

    def _get_options(self, selected_companies):
        """Report options standing on ``selected_companies[0]``, with those ticked."""
        report = self.report.with_context(allowed_company_ids=selected_companies.ids)
        return report, report.get_options({"selected_variant_id": report.id})

    def _settlement_button(self, options):
        """The button the gate governs, the one the assertions are about."""
        buttons = [button for button in options["buttons"] if button["name"].startswith(self.SETTLEMENT_TITLE)]
        self.assertEqual(len(buttons), 1, "the settlement button is what these tests observe")
        return buttons[0]

    def _get_warnings(self, selected_companies):
        report, options = self._get_options(selected_companies)
        warnings = {}
        report._generate_common_warnings(options, warnings)
        return options, warnings

    def test_warns_when_a_company_of_the_entity_is_not_selected(self):
        """The case the native code lets through: the book is partial and says nothing."""
        options, warnings = self._get_warnings(self.parent)

        self.assertNotIn(self.same_entity.id, self.report.get_report_company_ids(options))
        self.assertIn(self.MISSING_WARNING, warnings)
        self.assertIn(self.same_entity.name, warnings[self.MISSING_WARNING]["args"])

    def test_does_not_warn_about_companies_of_another_entity(self):
        """The one with a different Tax ID is not missing: it is not this legal entity."""
        _options, warnings = self._get_warnings(self.parent)

        self.assertIn(self.MISSING_WARNING, warnings)
        self.assertNotIn(self.other_entity.name, warnings[self.MISSING_WARNING]["args"])

    def test_does_not_warn_when_the_whole_entity_is_selected(self):
        _options, warnings = self._get_warnings(self.parent + self.same_entity)

        self.assertNotIn(self.MISSING_WARNING, warnings)

    def test_warns_on_every_report_and_not_only_on_the_tax_ones(self):
        """The scope is the legal entity, so the warning does not depend on the report.

        A report with ``filter_multi_company == 'selector'`` (our Balance, the General
        Ledger) has to claim the same thing as the VAT book: the companies of the legal
        entity that are not ticked are out of the numbers.
        """
        report = self.env.ref("account_reports.general_ledger_report")
        self.assertEqual(report.filter_multi_company, "selector")

        report = report.with_context(allowed_company_ids=self.parent.ids)
        options = report.get_options({"selected_variant_id": report.id})
        warnings = {}
        report._generate_common_warnings(options, warnings)

        self.assertIn(self.MISSING_WARNING, warnings)
        self.assertIn(self.same_entity.name, warnings[self.MISSING_WARNING]["args"])

    def test_export_buttons_ask_for_the_entity_and_not_for_the_whole_tree(self):
        """With the whole legal entity ticked the buttons work, even if the other is not.

        Without the hook the native gate is ``_all_branches_selected()``, which also
        demands the branch with a different Tax ID — the very one we want out of the
        report.
        """
        _report, options = self._get_options(self.parent + self.same_entity)

        self.assertFalse(self._settlement_button(options).get("error_action"))
        self.assertTrue(options.get("enable_export_buttons_for_common_vat_in_branches"))

    def test_export_buttons_stay_blocked_when_the_entity_is_incomplete(self):
        """Half a legal entity does not get exported: the native gate is still there."""
        _report, options = self._get_options(self.parent)

        self.assertEqual(self._settlement_button(options).get("error_action"), "show_error_branch_allowed")
