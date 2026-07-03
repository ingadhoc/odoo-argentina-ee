from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class AccountLoanLine(models.Model):
    _inherit = "account.loan.line"

    capital_move_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Capital Entry Line",
        readonly=True,
        copy=False,
        help="Payable line of the disbursement entry for this instalment's capital (empty on grace instalments).",
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Bill",
        readonly=True,
        copy=False,
    )
    is_grace_period = fields.Boolean(compute="_compute_is_grace_period", store=True)
    capital_reconciled = fields.Boolean(related="capital_move_line_id.reconciled", store=True)
    loan_is_ar_loan = fields.Boolean(related="loan_id.is_ar_loan")

    @api.depends("principal", "currency_id")
    def _compute_is_grace_period(self):
        for line in self:
            line.is_grace_period = line.currency_id.is_zero(line.principal)

    # -------------------------------------------------------------------------
    # US2 - Bill per instalment
    # -------------------------------------------------------------------------
    def action_generate_invoice(self):
        self.ensure_one()
        loan = self.loan_id
        if self.invoice_id:
            raise UserError(_("This instalment already has a bill."))
        if loan.currency_id.is_zero(self.interest):
            raise UserError(_("This instalment has no interest to bill."))
        if not loan.partner_id or not loan.interest_account_id:
            raise UserError(_("Set the bank contact and the interest account on the loan."))

        move = (
            self.env["account.move"]
            .with_company(loan.company_id)
            .create(
                {
                    "move_type": "in_invoice",
                    "company_id": loan.company_id.id,
                    "partner_id": loan.partner_id.id,
                    "invoice_date": self.date,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": _(
                                    "%(loan)s - Interest %(date)s",
                                    loan=loan.name,
                                    date=format_date(self.env, self.date, date_format="MM/y"),
                                ),
                                "quantity": 1.0,
                                "price_unit": self.interest,
                                "account_id": loan.interest_account_id.id,
                                "tax_ids": [Command.set(loan.interest_tax_ids.ids)],
                            }
                        )
                    ],
                }
            )
        )
        self.invoice_id = move
        return self.action_open_invoice()

    def action_open_invoice(self):
        self.ensure_one()
        return self.invoice_id._get_records_action(name=_("Loan Bill"))
