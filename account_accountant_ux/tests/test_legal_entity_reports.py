# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestLegalEntityReports(AccountTestInvoicingCommon):
    """The reporting side of "which companies are the same legal entity".

    The criterion itself lives in ``account_ux`` and the bridge to Enterprise in this
    module's ``res_company.py``; what is checked here is what does *not* come for free
    with that bridge:

    * that a report filed by Tax ID says something when it is run with only part of the
      legal entity, which is the case the native code does not cover —
      ``_get_branches_with_same_vat(accessible_only=True)`` silently drops the companies
      that are not ticked in the company selector;
    * that the settlement gate accepts what it should and refuses what cannot work.

    Scenario, all under the same root: a parent company with a Tax ID, two branches
    declaring the same one (the same legal entity, and sisters of each other) and a third
    one with a Tax ID of its own, which is a different legal entity.
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
        cls.branch = cls.env["res.company"].create(
            {"name": "Sucursal mismo CUIT", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT}
        )
        cls.sister = cls.env["res.company"].create(
            {"name": "Sucursal hermana", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT}
        )
        cls.other_entity = cls.env["res.company"].create(
            {"name": "Sucursal otro CUIT", "parent_id": cls.parent.id, "vat": cls.OTHER_VAT}
        )
        # The settlement button is this module's, and it is the one button the tests are
        # about, so they turn it on here instead of depending on whichever other module
        # installed on the database happens to add one.
        cls.report.write({"allow_settlement": True, "settlement_title": cls.SETTLEMENT_TITLE})

    def _get_options(self, selected_companies):
        """Report options standing on ``selected_companies[0]``, with those ticked."""
        report = self.report.with_context(allowed_company_ids=selected_companies.ids)
        return report, report.get_options({"selected_variant_id": report.id})

    def _settlement_button(self, options):
        """The button the gate used to govern, the one the assertions are about."""
        buttons = [button for button in options["buttons"] if button["name"].startswith(self.SETTLEMENT_TITLE)]
        self.assertEqual(len(buttons), 1, "the settlement button is what these tests observe")
        return buttons[0]

    def _get_warnings(self, selected_companies, report=None):
        report = (report or self.report).with_context(allowed_company_ids=selected_companies.ids)
        options = report.get_options({"selected_variant_id": report.id})
        warnings = {}
        report._generate_common_warnings(options, warnings)
        return options, warnings

    # -------------------------------------------------------------------------
    # The warning about the companies left out of a return
    # -------------------------------------------------------------------------

    def test_warns_when_a_company_of_the_entity_is_not_selected(self):
        """The case the native code lets through: the return is partial and says nothing."""
        options, warnings = self._get_warnings(self.parent)

        self.assertNotIn(self.branch.id, self.report.get_report_company_ids(options))
        self.assertIn(self.MISSING_WARNING, warnings)
        self.assertIn(self.branch.name, warnings[self.MISSING_WARNING]["args"])

    def test_does_not_warn_about_companies_of_another_entity(self):
        """The one with a different Tax ID is not missing: it is not this legal entity."""
        _options, warnings = self._get_warnings(self.parent)

        self.assertIn(self.MISSING_WARNING, warnings)
        self.assertNotIn(self.other_entity.name, warnings[self.MISSING_WARNING]["args"])

    def test_does_not_warn_when_the_whole_entity_is_selected(self):
        _options, warnings = self._get_warnings(self.parent + self.branch + self.sister)

        self.assertNotIn(self.MISSING_WARNING, warnings)

    def test_does_not_warn_on_a_report_whose_companies_come_from_the_selector(self):
        """On the General Ledger the user picked the companies: there is nothing to claim.

        Same guard the native warning next to this one uses. Without it the warning fires
        on every report, and on the ones filtered by the selector it is a false positive
        by design.
        """
        general_ledger = self.env.ref("account_reports.general_ledger_report")
        self.assertEqual(general_ledger.filter_multi_company, "selector")

        _options, warnings = self._get_warnings(self.parent, report=general_ledger)

        self.assertNotIn(self.MISSING_WARNING, warnings)

    def test_the_warning_is_worded_as_a_suggestion(self):
        """Filing part of an entity is allowed, so this is not an error."""
        _options, warnings = self._get_warnings(self.parent)

        self.assertEqual(warnings[self.MISSING_WARNING]["alert_type"], "info")

    # -------------------------------------------------------------------------
    # The settlement gate
    # -------------------------------------------------------------------------

    def _settle(self, selected_companies, journals=None):
        """Ask for the settlement wizard standing on ``selected_companies``."""
        report = self.report.with_context(allowed_company_ids=selected_companies.ids)
        options = report.get_options({"selected_variant_id": report.id})
        if journals is not None:
            options["journals"] = [{"id": journal.id, "model": "account.journal"} for journal in journals]
        return report.action_closure_journal_entry(options)

    def test_settlement_of_a_single_company_lands_on_that_company(self):
        """Managing it company by company is allowed: the entry goes where it was asked."""
        action = self._settle(self.branch)

        self.assertEqual(action["res_model"], "account.tax.settlement.wizard")
        self.assertEqual(action["context"]["default_company_id"], self.branch.id)

    def test_settlement_of_the_whole_entity_lands_on_its_head(self):
        """The suggested mode: one entry that reads like the return."""
        action = self._settle(self.parent + self.branch + self.sister)

        self.assertEqual(action["context"]["default_company_id"], self.parent.id)

    def test_settlement_of_a_parent_with_a_subset_of_its_branches_lands_on_the_parent(self):
        """Neither one company nor the whole entity, and it works: the parent files."""
        action = self._settle(self.parent + self.branch)

        self.assertEqual(action["context"]["default_company_id"], self.parent.id)

    def test_settlement_refuses_two_sisters_without_their_parent(self):
        """The one selection that cannot work, and the message says what to do about it.

        An account that lives only in one branch is not reachable from its sister
        (``check_companies_domain_parent_of``), so there is no company the entry could be
        built in.
        """
        with self.assertRaisesRegex(ValidationError, "is a parent of the others"):
            self._settle(self.branch + self.sister)

    def test_settlement_refuses_companies_of_different_legal_entities(self):
        """Tax IDs are never mixed, whatever else the selection looks like."""
        with self.assertRaisesRegex(ValidationError, "never filed across Tax IDs"):
            self._settle(self.parent + self.branch + self.other_entity)

    def test_settlement_does_not_look_at_who_owns_the_journals(self):
        """The bug the gate replaces: journals of the parent used to pass anything.

        The previous gate read the companies of the journals picked in the report and
        demanded exactly one, so this selection —two sisters, half the entity, with every
        journal belonging to the parent— went through unnoticed. The gate looks at
        ``env.companies`` now, so it does not.
        """
        journals = self.env["account.journal"].create(
            [
                {"name": "Settlement parent", "code": "STLP", "type": "general", "company_id": self.parent.id},
                {"name": "Settlement parent 2", "code": "STLQ", "type": "general", "company_id": self.parent.id},
            ]
        )

        with self.assertRaisesRegex(ValidationError, "is a parent of the others"):
            self._settle(self.branch + self.sister, journals=journals)

    def test_the_settlement_button_is_never_gated_by_the_native_check(self):
        """Whatever the gate accepts has to be clickable, or the modes are unreachable.

        A single branch is a valid settlement and it is never ``_all_branches_selected``,
        so the button cannot rely on the native gate — nor on the Enterprise hook that
        softens it, which only accepts the whole group sharing a Tax ID.
        """
        _report, options = self._get_options(self.branch)

        self.assertTrue(self._settlement_button(options)["branch_allowed"])
        self.assertFalse(self._settlement_button(options).get("error_action"))
        self.assertFalse(options.get("enable_export_buttons_for_common_vat_in_branches"))

    def test_reports_without_settlement_are_left_alone(self):
        """The override claims nothing on a report that does not carry the button."""
        general_ledger = self.env.ref("account_reports.general_ledger_report")
        report = general_ledger.with_context(allowed_company_ids=self.parent.ids)

        options = report.get_options({"selected_variant_id": report.id})

        self.assertFalse(options.get("enable_export_buttons_for_common_vat_in_branches"))
        self.assertFalse([button for button in options["buttons"] if button["name"].startswith(self.SETTLEMENT_TITLE)])

    # -------------------------------------------------------------------------
    # What the gate lets through and the ORM would not
    # -------------------------------------------------------------------------

    def test_an_account_living_only_in_a_branch_is_named_before_the_orm_complains(self):
        """The price of accepting a subset: the entry has to say which account it cannot use."""
        branch_account = (
            self.env["account.account"]
            .with_company(self.branch)
            .create(
                {
                    "name": "Resultado de la sucursal",
                    "code": "BRA001",
                    "account_type": "expense",
                    "company_ids": [(6, 0, self.branch.ids)],
                }
            )
        )

        with self.assertRaisesRegex(ValidationError, "Resultado de la sucursal"):
            self.report._check_settlement_accounts_are_reachable(branch_account, self.parent)

    def test_an_account_of_the_parent_is_reachable_from_the_parent_and_its_branches(self):
        parent_account = (
            self.env["account.account"]
            .with_company(self.parent)
            .create(
                {
                    "name": "Resultado de la casa matriz",
                    "code": "PAR001",
                    "account_type": "expense",
                    "company_ids": [(6, 0, self.parent.ids)],
                }
            )
        )

        self.report._check_settlement_accounts_are_reachable(parent_account, self.parent)
        self.report._check_settlement_accounts_are_reachable(parent_account, self.branch)

    # -------------------------------------------------------------------------
    # Settling the same period twice
    # -------------------------------------------------------------------------

    def _settlement_move(self, company, date):
        journal = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "general")], limit=1
        ) or self.env["account.journal"].create(
            {"name": "Diario general", "code": "GEN99", "type": "general", "company_id": company.id}
        )
        return (
            self.env["account.move"]
            .with_company(company)
            .create({"journal_id": journal.id, "date": date, "ref": self.SETTLEMENT_TITLE})
        )

    def _wizard_defaults(self, report, options, company):
        return (
            self.env["account.tax.settlement.wizard"]
            .with_context(
                default_report_id=report.id,
                default_company_id=company.id,
                account_report_generation_options=options,
            )
            .default_get(["already_settled_warning"])
        )

    def test_the_wizard_says_when_the_period_was_already_settled(self):
        """A warning and not a block: a second entry may well be a correction."""
        report, options = self._get_options(self.parent)
        self._settlement_move(self.parent, options["date"]["date_to"])

        defaults = self._wizard_defaults(report, options, self.parent)

        self.assertIn(self.parent.name, defaults["already_settled_warning"])

    def test_the_wizard_says_nothing_when_another_company_settled(self):
        """Each company files its own: a branch's entry is not the parent's."""
        report, options = self._get_options(self.parent)
        self._settlement_move(self.branch, options["date"]["date_to"])

        defaults = self._wizard_defaults(report, options, self.parent)

        self.assertFalse(defaults.get("already_settled_warning"))

    def test_the_wizard_says_nothing_when_the_period_is_clean(self):
        report, options = self._get_options(self.parent)

        defaults = self._wizard_defaults(report, options, self.parent)

        self.assertFalse(defaults.get("already_settled_warning"))
