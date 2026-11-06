# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from unittest.mock import patch

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestLegalEntityReturns(AccountTestInvoicingCommon):
    """A simple closing return closes the whole legal entity in a single entry.

    Scenario: a parent with two branches declaring the same Tax ID and one sale in each.
    """

    PARENT_VAT = "30111111118"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.company_data["company"]
        cls.parent.vat = cls.PARENT_VAT
        cls.branch_1 = cls._create_company(name="Sucursal Rosario", parent_id=cls.parent.id, vat=cls.PARENT_VAT)
        cls.branch_2 = cls._create_company(name="Sucursal Córdoba", parent_id=cls.parent.id, vat=cls.PARENT_VAT)
        cls.entity = cls.parent + cls.branch_1 + cls.branch_2
        cls.env.user.company_ids |= cls.entity

        cls.invoices = cls.env["account.move"]
        for company, amount in ((cls.parent, 1000.0), (cls.branch_1, 500.0), (cls.branch_2, 300.0)):
            cls.invoices |= cls._create_invoice(
                move_type="out_invoice",
                invoice_date="2026-08-15",
                post=True,
                company_id=company.id,
                invoice_line_ids=[cls._prepare_invoice_line(product_id=cls.product_a, price_unit=amount)],
            )
        cls.tax_total = sum(cls.invoices.mapped("amount_tax"))

        report = cls.env["account.report"].create(
            {"root_report_id": cls.env.ref("account.generic_tax_report").id, "name": "Legal entity tax report"}
        )
        cls.ar_return_type = cls.env["account.return.type"].create(
            {
                "name": "IVA (legal entity)",
                "report_id": report.id,
                "country_id": cls.env.ref("base.ar").id,
                "payment_partner_id": cls.partner_a.id,
            }
        )
        cls.generic_return_type = cls.env["account.return.type"].create(
            {"name": "VAT (generic)", "report_id": report.id}
        )

    def _create_return(self, return_type, selected_companies):
        tax_return = self.env["account.return"].create(
            {
                "name": "IVA agosto 2026",
                "type_id": return_type.id,
                "company_id": self.parent.id,
                "date_from": "2026-08-01",
                "date_to": "2026-08-31",
            }
        )
        self.assertEqual(tax_return.company_ids, self.entity, "the return holds the whole legal entity")
        return tax_return.with_context(allowed_company_ids=selected_companies.ids)

    def _closing_vals(self, return_type, selected_companies):
        tax_return = self._create_return(return_type, selected_companies)
        return tax_return._generate_tax_closing_entries_create_values(tax_return._get_closing_report_options())

    def test_validate_posts_one_entry_for_the_whole_legal_entity(self):
        """Even with only the parent ticked: one balanced entry, the whole tax against the payment partner."""
        tax_return = self._create_return(self.ar_return_type, self.parent)
        with patch.object(self.registry["account.return"], "_generate_locking_attachments", lambda self, options: None):
            tax_return.action_validate(bypass_failing_tests=True)

        move = tax_return.closing_move_ids
        self.assertEqual(len(move), 1)
        self.assertEqual(move.company_id, self.parent)
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0)
        payment_line = move.line_ids.filtered(lambda line: line.partner_id == self.partner_a)
        self.assertAlmostEqual(payment_line.balance, -self.tax_total)
        self.assertAlmostEqual(tax_return.period_amount_to_pay, self.tax_total)

    def test_refuses_to_validate_without_the_company_of_the_return(self):
        with self.assertRaisesRegex(UserError, self.parent.name):
            self._closing_vals(self.ar_return_type, self.branch_1)

    def test_refuses_accounts_that_live_only_in_a_branch(self):
        """The parent cannot use them, so the message names them instead of the ORM company check."""
        branch_account = self.env["account.account"].create(
            {
                "name": "IVA débito sucursal",
                "code": "214999",
                "account_type": "liability_current",
                "company_ids": [Command.set(self.branch_1.ids)],
            }
        )
        branch_tax = self.tax_sale_a.copy({"name": "IVA 21% sucursal", "company_id": self.branch_1.id})
        branch_tax.invoice_repartition_line_ids.filtered(
            lambda line: line.repartition_type == "tax"
        ).account_id = branch_account
        self._create_invoice(
            move_type="out_invoice",
            invoice_date="2026-08-20",
            post=True,
            company_id=self.branch_1.id,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_a, price_unit=100.0, tax_ids=branch_tax)
            ],
        )

        with self.assertRaisesRegex(UserError, branch_account.name):
            self._closing_vals(self.ar_return_type, self.entity)

    def test_other_return_types_keep_one_entry_per_company(self):
        self.assertEqual(len(self._closing_vals(self.generic_return_type, self.entity)), 3)
