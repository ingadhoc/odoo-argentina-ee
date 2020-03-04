# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in root directory
##############################################################################
from odoo import api, fields, models
# import datetime
from dateutil.relativedelta import relativedelta


class AccountJournalBookReport(models.TransientModel):
    _inherit = "account.common.report"
    _name = "account.journal.book.report"
    _description = "Journal Book Report"

    # este campo ya existe en la clase oficial, lo recreamos
    # para cambiar la rel
    journal_ids = fields.Many2many(
        'account.journal',
        'account_journal_book_journal_rel',
        'acc_journal_entries_id',
        'journal_id',
        'Journals',
        required=True,
        ondelete='cascade',
    )
    last_entry_number = fields.Integer(
        string='Último número de asiento',
        required=True,
        default=0,
    )
    date_from = fields.Date(
        required=True,
    )
    date_to = fields.Date(
        required=True,
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        dates = self.company_id.compute_fiscalyear_dates(
            fields.Date.from_string(fields.Date.today()))
        if dates:
            self.date_from = dates['date_from']
            self.date_to = dates['date_to']

    def _print_report(self, data):
        date_from = fields.Date.from_string(self.date_from)
        date_to = fields.Date.from_string(self.date_to)
        periods = []
        # por mas que el usuario pida fecha distinta al 1 del mes, los move
        # lines ya van a estar filtrados por esa fecha y por simplicidad
        # construimos periodos desde el 1
        dt_from = date_from.replace(day=1)
        while dt_from < date_to:
            dt_to = dt_from + relativedelta(months=1, days=-1)
            periods.append((fields.Date.to_string(dt_from),
                            fields.Date.to_string(dt_to)))
            # este va a se la date from del proximo
            dt_from = dt_to + relativedelta(days=1)
        domain = [('company_id', '=', self.company_id.id)]
        if self.target_move == 'posted':
            domain.append(('state', '=', 'posted'))
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        moves = self.env['account.move'].search(domain)
        return self.env['ir.actions.report'].search(
            [('report_name', '=', 'account_journal_book_report')], limit=1
        ).with_context(
            periods=periods,
            last_entry_number=self.last_entry_number,
        ).report_action(moves)
