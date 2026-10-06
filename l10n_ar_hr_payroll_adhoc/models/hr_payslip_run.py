from odoo import fields, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    l10n_ar_payment_date = fields.Date("Payment Date")
    l10n_ar_contribution_date = fields.Date(
        "Contributions Payment Date",
        help="Date of the last social security deposit, shown on the payslip.",
    )

    def action_l10n_ar_register_payments(self):
        """Open the payment wizard with one net-salary line per employee, so each one gets its own payment."""
        slips = self.slip_ids.filtered(lambda s: s.move_id.state == "posted")
        net_accounts = slips.struct_id.rule_ids.filtered(lambda r: r.code == "NET").account_credit
        lines = slips.move_id.line_ids.filtered(
            lambda l: l.account_id in net_accounts and l.partner_id and l.credit and not l.reconciled
        )
        if not lines:
            raise UserError(
                self.env._(
                    "There are no pending salaries to pay. Check that the journal entry is posted and that the NET "
                    'rule has a reconcilable credit account and "Set employee on account line".'
                )
            )
        return lines.action_register_payment(ctx={"hr_payroll_payment_register": True})
