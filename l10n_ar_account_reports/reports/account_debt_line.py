from odoo import models, fields, api


class AccountDebtLine(models.Model):
    _inherit = "account.debt.line"

    expected_pay_date = fields.Date(
        'Expected Payment Date',
        compute='_compute_move_lines_data',
        help="Expected payment date as manually set through the customer "
        "statement (e.g: if you had the customer on the phone and want to "
        "remember the date he promised he would pay)"
    )
    internal_note = fields.Text(
        'Internal Note',
        compute='_compute_move_lines_data',
        help="Note you can set through the customer statement about a "
        "receivable journal item"
    )
    next_action_date = fields.Date(
        'Next Action Date',
        compute='_compute_move_lines_data',
        help="Date where the next action should be taken for a receivable "
        "item. Usually, automatically set when sending reminders through the "
        "customer statement."
    )

    @api.multi
    def _compute_move_lines_data(self):
        res = super(AccountDebtLine, self)._compute_move_lines_data()
        for rec in self:
            rec.expected_pay_date = rec.move_line_id.expected_pay_date
            rec.internal_note = rec.move_line_id.internal_note
            rec.next_action_date = rec.move_line_id.next_action_date
        return res
