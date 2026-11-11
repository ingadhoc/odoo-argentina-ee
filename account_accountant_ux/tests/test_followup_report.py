# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from dateutil.relativedelta import relativedelta
from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestFollowupReport(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("account_reports.followup_report")
        cls.today = fields.Date.today()

    def test_paid_lines_in_partial_reconciliation_chain(self):
        """Given a payment that pays one invoice and part of another, when the followup report is
        opened, then it shows the open invoice but not the paid invoice nor the payment."""
        invoice_date = self.today - relativedelta(days=30)
        invoices = self.env["account.move"]
        for _i in range(2):
            invoice = self.init_invoice(
                "out_invoice", partner=self.partner_a, invoice_date=invoice_date, amounts=[100.0]
            )
            invoice.invoice_payment_term_id = False
            invoice.invoice_date_due = invoice_date
            invoice.action_post()
            invoices |= invoice
        invoice_paid, invoice_open = invoices
        payment = self.env["account.payment"].create(
            {"payment_type": "inbound", "partner_type": "customer", "partner_id": self.partner_a.id, "amount": 150.0}
        )
        payment.action_post()
        (invoices.line_ids | payment.move_id.line_ids).filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        ).reconcile()
        # The chain stays open, so the paid invoice has no full reconciliation.
        self.assertFalse(invoice_paid.line_ids.full_reconcile_id)

        line_names = [line.name for line in self._get_report_lines()]
        self.assertIn(invoice_open.name, line_names)
        self.assertNotIn(invoice_paid.name, line_names)
        self.assertNotIn(payment.move_id.name, line_names)

    def test_partner_total_due_and_overdue_lines(self):
        """Given an overdue invoice and one not yet due, when the followup report is opened, then the
        partner shows Total Due with both residuals and Total Overdue with only the overdue one."""
        for days_due, amount in ((-30, 100.0), (10, 50.0)):
            invoice = self.init_invoice(
                "out_invoice",
                partner=self.partner_a,
                invoice_date=self.today - relativedelta(days=40),
                amounts=[amount],
            )
            invoice.invoice_payment_term_id = False
            invoice.invoice_date_due = self.today + relativedelta(days=days_due)
            invoice.invoice_line_ids.tax_ids = False
            invoice.action_post()

        lines = self._get_report_lines()
        residual_index = next(
            i for i, column in enumerate(lines[0].columns) if column.expression_label == "amount_residual"
        )
        totals = {
            self.report._get_markup(line.id): line.columns[residual_index].no_format
            for line in lines
            if self.report._get_markup(line.id) in ("total_due", "total_overdue")
        }
        self.assertEqual(totals, {"total_due": 150.0, "total_overdue": 100.0})

    def test_partner_totals_exclude_no_followup_lines(self):
        """Given two overdue invoices, one marked no follow-up, when the partner totals are computed, then
        they count only the other one, as the follow-up report does."""
        invoices = self.env["account.move"]
        for amount in (100.0, 40.0):
            invoice = self.init_invoice(
                "out_invoice",
                partner=self.partner_a,
                invoice_date=self.today - relativedelta(days=40),
                amounts=[amount],
            )
            invoice.invoice_payment_term_id = False
            invoice.invoice_date_due = self.today - relativedelta(days=30)
            invoice.invoice_line_ids.tax_ids = False
            invoice.action_post()
            invoices |= invoice
        invoices[1].line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        ).no_followup = True

        partner = self.partner_a.with_company(self.env.company)
        self.assertRecordValues(
            partner,
            [
                {
                    "total_all_due": 100.0,
                    "total_all_due_abs": 100.0,
                    "total_all_overdue": 100.0,
                    "total_due": 100.0,
                    "total_overdue": 100.0,
                }
            ],
        )

    def _get_report_lines(self):
        options = self.report.get_options(
            {
                "selected_variant_id": self.report.id,
                "date": {
                    "date_from": fields.Date.to_string(self.today - relativedelta(days=60)),
                    "date_to": fields.Date.to_string(self.today),
                    "mode": "range",
                    "filter": "custom",
                },
            }
        )
        options["unfold_all"] = True
        return self.report._get_lines(options)
