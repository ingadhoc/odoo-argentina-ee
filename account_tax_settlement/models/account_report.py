from odoo import models, _
from odoo.exceptions import ValidationError


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    def _init_options_buttons(self, options, previous_options=None):
        super()._init_options_buttons(options, previous_options)
        # TODO en vez de hacerlo por xmlid podamos agregar un campo en
        # account.report o algo por el estilo
        if self == self.env.ref('account_reports.profit_and_loss'):
            options.setdefault('buttons', []).append({
                'name': 'Generar asiento de refundición (BETA)',
                'sequence': 150,
                'action': 'action_closure_journal_entry',
            })
        elif self == self.env.ref('account_reports.balance_sheet'):
            options.setdefault('buttons', []).append({
                'name': 'Generar asiento de cierre (BETA)',
                'sequence': 50,
                'action': 'action_closure_journal_entry',
            })

    def action_closure_journal_entry(self, options):
        """ Abrimos wizard de liquidación para que se elija diario
        """
        self.ensure_one()

        companies = self.env['account.journal'].browse([x['id'] for x in options.get('journals')]).mapped('company_id')
        if len(companies) != 1:
            raise ValidationError(_('La liquidación se debe realizar filtrando por 1 y solo 1 compañía en el reporte'))
        if self == self.env.ref('account_reports.profit_and_loss'):
            action_name = 'Generar asiento de refundición (BETA)'
            entry_ref = 'Asiento de refundición'
            default_message = 'Se va a generar el asiento de refundición a partir de los datos visualizados'
        elif self == self.env.ref('account_reports.balance_sheet'):
            action_name = 'Generar asiento de cierre (BETA)'
            entry_ref = 'Asiento de cierre'
            default_message = (
                'Antes de generar el asiento de cierre recuerde generar el asiento de refundición. '
                'Luego de generar el asiento de cierre recuerde revertirlo para generar el asiento de apertura!')

        new_context = {
            **self._context,
            'account_report_generation_options': options,
            'default_report_id': self.id,
            'default_message': default_message,
            'entry_ref': entry_ref,
            'default_company_id': companies.id,
        }
        view_id = self.env.ref('account_tax_settlement.view_account_tax_settlement_wizard_form').id

        return {
            'type': 'ir.actions.act_window',
            'name': action_name,
            'view_mode': 'form',
            'res_model': 'account.tax.settlement.wizard',
            'target': 'new',
            'views': [[view_id, 'form']],
            'context': new_context,
        }

    def _report_create_settlement_entry(self, journal, options):
        """
        Funcion que crea asiento de liquidación a partir de información del
        reporte y devuelve browse del asiento generado
        * from_report_id
        * force_context
        * context: periods_number, cash_basis, date_filter_cmp, date_filter,
        date_to, date_from, hierarchy_3, company_ids, date_to_cmp,
        date_from_cmp, all_entries
        * search_disable_custom_filters
        * from_report_model
        * active_id
        """
        self.ensure_one()
        raise ValidationError('Esta funcionalidad todavía no ha sido implmentada. Por favor contacte a mesa de ayuda')
