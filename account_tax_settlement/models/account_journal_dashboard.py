from odoo import models
from odoo.tools.misc import formatLang


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def get_journal_dashboard_datas(self):
        res = super(AccountJournal, self).get_journal_dashboard_datas()
        currency = self.currency_id or self.company_id.currency_id
        # TODO hacer por sql por temas de performance?
        unsettled_lines = self._get_tax_settlement_move_lines_by_tags()
        res.update({
            # los importes estan en la moneda de la cia, sin importar el diario
            'unsettled_count': len(unsettled_lines),
            'unsettled_amount': formatLang(self.env, -sum(unsettled_lines.mapped('balance')), currency_obj=currency),
            'debit_amount': formatLang(self.env, self.settlement_partner_id.debit, currency_obj=currency),
        })
        return res

    def open_action(self):
        """
        Modificamos funcion para que si es liquidacion de impuestos devuelva accion correspondiente
        Y si es deuda del partner muestre el partner ledger
        """
        if self.type == 'general' and self.tax_settlement:
            tax_settlement = self._context.get('tax_settlement', False)
            debt_balance = self._context.get('debt_balance', False)
            if tax_settlement:
                action = self.env["ir.actions.actions"]._for_xml_id('account_tax_settlement.action_account_tax_move_line')
                action['domain'] = self._get_tax_settlement_lines_domain_by_tags()
                return action
            elif debt_balance and self.settlement_partner_id:
                action = self.settlement_partner_id.open_partner_ledger()
                ctx = action.get('context')
                ctx.update({
                    'default_partner_id': self.settlement_partner_id.id,
                })
                action['context'] = ctx
                return action
        return super(AccountJournal, self).open_action()
