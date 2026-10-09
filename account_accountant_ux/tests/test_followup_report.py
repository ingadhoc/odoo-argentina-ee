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

        date_from = fields.Date.to_string(self.today - relativedelta(days=60))
        options = self.report.get_options(
            {
                "selected_variant_id": self.report.id,
                "date": {
                    "date_from": date_from,
                    "date_to": fields.Date.to_string(self.today),
                    "mode": "range",
                    "filter": "custom",
                },
            }
        )
        options["unfolded_lines"] = [self.report._get_generic_line_id("res.partner", self.partner_a.id)]
        line_names = [line["name"] for line in self.report._get_lines(options)]
        self.assertIn(invoice_open.name, line_names)
        self.assertNotIn(invoice_paid.name, line_names)
        self.assertNotIn(payment.move_id.name, line_names)
