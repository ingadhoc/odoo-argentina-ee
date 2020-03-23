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
    )
    report_id = fields.Many2one(
        'account.financial.html.report',
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
    message = fields.Text(
    )

    @api.model
    def default_get(self, fields):
        res = super(AccountTaxSettlementWizard, self).default_get(fields)

        report = self.env['account.financial.html.report'].browse(
            self._context.get('from_report_id'))

        active_model = self._context.get('active_model')
        if not report and active_model != 'account.move.line':
            raise ValidationError(_(
                'No "from_report_id" key on context and report not called '
                'from journal entries'))

        # solo si es del tipo reporte se devuelven estos campos
        if not report:
            active_ids = self._context.get('active_ids')
            res.update({'move_line_ids': active_ids})
            return res

        company_ids = self._context.get('context', {}).get('company_ids')

        if not company_ids or len(company_ids) != 1:
            raise ValidationError(_(
                'La liquidación se debe realizar filtrando por 1 y solo 1 '
                'compañía en el reporte'))

        journal = self.env['account.journal'].search([
            ('settlement_financial_report_id', '=', report.id),
            ('company_id', '=', company_ids[0])], limit=1)

        res.update({
            'settlement_journal_id': journal.id,
            'report_id': report.id,
            'company_id': company_ids[0],
            'select_journal': not bool(journal),
            # 'select_journal': not bool(journal) and False or True,
        })
        return res

    def confirm(self):
        self.ensure_one()
        self = self.with_context(entry_date=self.date)
        if self.report_id:
            move = self.report_id.create_tax_settlement_entry(
                self.settlement_journal_id)
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
