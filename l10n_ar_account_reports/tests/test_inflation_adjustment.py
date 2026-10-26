# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import date

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestInflationAdjustmentLegalEntity(AccountTestInvoicingCommon):
    """The inflation adjustment follows the company selector, like the settlement entries.

    Scenario, all under the same root: a parent company with a Tax ID, two branches
    declaring the same one (the same legal entity, and sisters of each other) and a third
    one with a Tax ID of its own, which is a different legal entity.
    """

    PARENT_VAT = "30111111118"
    OTHER_VAT = "30999999995"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        cls.parent = Company.create({"name": "Casa Matriz", "vat": cls.PARENT_VAT})
        cls.branch = Company.create({"name": "Sucursal mismo CUIT", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT})
        cls.sister = Company.create({"name": "Sucursal hermana", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT})
        cls.other_entity = Company.create(
            {"name": "Sucursal otro CUIT", "parent_id": cls.parent.id, "vat": cls.OTHER_VAT}
        )
        cls.expense_account = cls._create_parent_account("Gastos", "INF001", "expense")
        cls.cash_account = cls._create_parent_account("Caja", "INF002", "asset_current")
        cls.recpam_account = cls._create_parent_account("RECPAM", "INF003", "expense")
        cls.journals = {
            company: cls.env["account.journal"].create(
                {"name": "Varios %s" % company.name, "code": "INF%s" % i, "type": "general", "company_id": company.id}
            )
            for i, company in enumerate(cls.parent + cls.branch + cls.sister + cls.other_entity)
        }
        # Far in the past, so they never clash with the indexes the module loads.
        for month, value in ((date(1989, 12, 1), 100.0), (date(1990, 1, 1), 110.0), (date(1990, 2, 1), 121.0)):
            cls.env["inflation.adjustment.index"].create({"date": month, "value": value})

    @classmethod
    def _create_parent_account(cls, name, code, account_type):
        return (
            cls.env["account.account"]
            .with_company(cls.parent)
            .create({"name": name, "code": code, "account_type": account_type, "company_ids": [(6, 0, cls.parent.ids)]})
        )

    def _post_expense(self, company, amount):
        move = (
            self.env["account.move"]
            .with_company(company)
            .create(
                {
                    "journal_id": self.journals[company].id,
                    "date": date(1990, 1, 15),
                    "line_ids": [
                        (0, 0, {"account_id": self.expense_account.id, "debit": amount}),
                        (0, 0, {"account_id": self.cash_account.id, "credit": amount}),
                    ],
                }
            )
        )
        move.action_post()
        return move

    def _wizard(self, selected_companies):
        Wizard = self.env["inflation.adjustment"].with_context(allowed_company_ids=selected_companies.ids)
        return Wizard.create(
            {
                "date_from": date(1990, 1, 1),
                "date_to": date(1990, 2, 28),
                "journal_id": self.journals[self.parent].id,
                "account_id": self.recpam_account.id,
            }
        )

    def test_adjusts_the_selected_companies_in_their_head(self):
        """Standing on a branch with its parent ticked, the entry lands on the parent."""
        self._post_expense(self.parent, 1000.0)
        self._post_expense(self.branch, 500.0)
        self._post_expense(self.sister, 300.0)

        wizard = self._wizard(self.branch + self.parent)

        self.assertEqual(wizard.company_id, self.parent)
        self.assertIn(self.sister.name, wizard.missing_companies_warning)
        move = self.env["account.move"].browse(wizard.confirm()["res_id"])
        self.assertEqual(move.company_id, self.parent)
        adjusted = sum(move.line_ids.filtered(lambda line: line.account_id == self.expense_account).mapped("balance"))
        # 1500 of January, adjusted by 121 / 110 - 1. The sister is not selected, so it is not in.
        self.assertAlmostEqual(adjusted, 150.0, places=2)

    def test_excludes_the_entries_of_each_selected_company(self):
        entries = self._post_expense(self.parent, 1000.0) | self._post_expense(self.branch, 500.0)
        wizard = self._wizard(self.parent + self.branch)
        wizard.write({"open_cloure_entry": "yes", "open_move_ids": [(6, 0, entries.ids)]})

        with self.assertRaisesRegex(UserError, "No journal entries to adjust"):
            wizard.confirm()

    def test_names_companies_with_no_entries_once_a_branch_has_its_own(self):
        parent_entry = self._post_expense(self.parent, 1000.0)
        branch_entry = self._post_expense(self.branch, 500.0)
        wizard = self._wizard(self.parent + self.branch + self.sister)
        wizard.write(
            {
                "open_cloure_entry": "yes",
                "closure_move_ids": [(6, 0, parent_entry.ids)],
                "open_move_ids": [(6, 0, parent_entry.ids)],
            }
        )

        # Only the head's entries: the entity closes there, nothing to warn about.
        self.assertFalse(wizard.missing_entries_warning)

        wizard.write({"closure_move_ids": [(4, branch_entry.id)], "open_move_ids": [(4, branch_entry.id)]})

        self.assertIn(self.sister.name, wizard.missing_entries_warning)
        self.assertNotIn(self.branch.name, wizard.missing_entries_warning)

    def test_refuses_selections_with_no_filing_company(self):
        with self.assertRaisesRegex(UserError, "never done across Tax IDs"):
            self._wizard(self.parent + self.other_entity).confirm()
        with self.assertRaisesRegex(UserError, "is a parent of the others"):
            self._wizard(self.branch + self.sister).confirm()

    def test_names_the_accounts_the_filing_company_cannot_use(self):
        branch_account = (
            self.env["account.account"]
            .with_company(self.branch)
            .create(
                {
                    "name": "Gastos de la sucursal",
                    "code": "INF004",
                    "account_type": "expense",
                    "company_ids": [(6, 0, self.branch.ids)],
                }
            )
        )
        move = self._post_expense(self.branch, 500.0)
        move.button_draft()
        move.line_ids.filtered(lambda line: line.account_id == self.expense_account).account_id = branch_account
        move.action_post()

        with self.assertRaisesRegex(UserError, "Gastos de la sucursal"):
            self._wizard(self.parent + self.branch).confirm()
