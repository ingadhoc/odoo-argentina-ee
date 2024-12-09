##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class AccountTaxSettlementWizard(models.TransientModel):
    """
    Wizard para liquidar impuestos desde reportes o desde selección de
    múltiples apuntes contables. Puede ser extendido para agregar cualquier
    otro datos que sea necesario
    """
    _name = 'account.tax.settlement.wizard'
    _description = 'Wizard para generar liquidaciones de impuestos desde '
    'reportes'

    date = fields.Date(
        'Journal Entry Date',
        required=True,
        default=fields.Date.context_today,
    )
    settlement_journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        check_company=True,
        domain=[('type', '=', 'general')]
    )
    report_id = fields.Many2one(
        'account.report',
    )
    move_line_ids = fields.Many2many(
        'account.move.line',
    )
    # fields used to make a settlement from reports without a journal
    select_journal = fields.Boolean(
    )
    company_id = fields.Many2one(
        'res.company',
    )
    account_id = fields.Many2one(
        'account.account',
        check_company=True,
        domain=[('deprecated', '=', False)]
    )
    report_settlement_allow_unbalanced = fields.Boolean(
        related='report_id.settlement_allow_unbalanced',
    )

    @api.model
    def default_get(self, fields):
        res = super(AccountTaxSettlementWizard, self).default_get(fields)
        if self._context.get('active_model') == 'account.move.line':
            active_ids = self._context.get('active_ids')
            res.update({'move_line_ids': active_ids})
            return res
        return res

    def confirm(self):
        self.ensure_one()
        self = self.with_context(entry_date=self.date)
        if self.report_id:
            move = self.report_id.with_context(skip_invoice_sync=True)._report_create_settlement_entry(
                self.settlement_journal_id, options=self._context.get('account_report_generation_options'),
                account=self.account_id)
        else:
            move = self.move_line_ids.create_tax_settlement_entry()
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.move',
            'target': 'current',
            'res_id': move.id,
            'type': 'ir.actions.act_window',
        }
