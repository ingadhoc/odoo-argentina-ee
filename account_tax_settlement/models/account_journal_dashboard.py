from odoo import models
from odoo.tools.misc import formatLang
from odoo.tools.safe_eval import safe_eval

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _get_journal_dashboard_data_batched(self):
        res = super(AccountJournal, self)._get_journal_dashboard_data_batched()
        self._fill_tax_settlement_dashboard_data(res)
        return res

    def _fill_tax_settlement_dashboard_data(self, dashboard_data):
        """ En diarios de liquidación en vista kanban agregamos al lado del botoncitos 'Líneas a liquidar' la cantidad de líneas de liquidar y el importe y al lado del botoncito 'Saldo a pagar' agregamos el importe """
        tax_settlement_journals = self.filtered(lambda journal: journal.tax_settlement != False)
        if not tax_settlement_journals:
            return
        # TODO hacer por sql para mejorar performance
        for journal in tax_settlement_journals:
            currency = journal.currency_id or journal.company_id.currency_id
            unsettled_lines = journal._get_tax_settlement_move_lines_by_tags()
            dashboard_data[journal.id].update({
                'unsettled_count': len(unsettled_lines),
                'unsettled_amount': formatLang(self.env, -sum(unsettled_lines.mapped('balance')), currency_obj=currency),
                'debit_amount': formatLang(self.env, journal.settlement_partner_id.debit, currency_obj=currency),
            })

    def open_action(self):
        """
        Modificamos funcion para que si es liquidacion de impuestos devuelva accion correspondiente
        Y si es deuda del partner muestre el partner ledger
        """
        if self.type == 'general' and self.tax_settlement:
            tax_settlement = self._context.get('tax_settlement', False)
            debt_balance = self._context.get('debt_balance', False)
            if tax_settlement:
                # Ingresa aquí al entrar en vista Kanban en diario de liquidacion en el botoncito "Líneas a liquidar"
                action = self.env["ir.actions.actions"]._for_xml_id('account_tax_settlement.action_account_tax_move_line')
                action['domain'] = self._get_tax_settlement_lines_domain_by_tags()
                return action
            elif debt_balance and self.settlement_partner_id:
                # Ingresa aquí al entrar en vista Kanban en diario de liquidacion en el botoncito 'Saldo a pagar'
                action = self.settlement_partner_id.open_partner_ledger()
                ctx = safe_eval(action.get('context'))
                ctx.update({
                    'default_partner_id': self.settlement_partner_id.id,
                })
                action['context'] = ctx
                return action
        return super(AccountJournal, self).open_action()
