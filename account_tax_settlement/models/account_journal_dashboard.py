from odoo import fields, models, api
from odoo.tools.misc import formatLang
from dateutil.relativedelta import relativedelta
import datetime


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def get_journal_dashboard_datas(self):
        res = super(AccountJournal, self).get_journal_dashboard_datas()
        company = self.company_id
        currency = self.currency_id or self.company_id.currency_id
        report_position = 0.0

        # TODO hacer por sql por temas de performance?
        unsettled_lines = self._get_tax_settlement_move_lines_by_tags()
        tax_lines = self.env['account.move.line'].search(
            self._get_tax_settlement_lines_domain_by_tags_accounts())
        res.update({
            # los importes estan en la moneda de la cia, sin importar el diario
            'report_position': formatLang(
                self.env, report_position, currency_obj=currency),
            'unsettled_count': len(unsettled_lines),
            'unsettled_amount': formatLang(
                self.env, -sum(unsettled_lines.mapped('balance')),
                currency_obj=currency),
            'tax_balance': formatLang(
                self.env, -sum(tax_lines.mapped('balance')),
                currency_obj=currency),
            'debit_amount': formatLang(
                self.env, self.settlement_partner_id.debit,
                currency_obj=currency),
        })
        return res

    def open_action(self):
        """
        Modificamos funcion para que si hay un reporte vinculado
        la posición muestre el reporte
        """
        if self.type == 'general' and self.tax_settlement:
            tax_settlement = self._context.get('tax_settlement', False)
            accounts_balance = self._context.get('accounts_balance', False)
            open_report = self._context.get('open_report', False)
            debt_balance = self._context.get('debt_balance', False)
            if tax_settlement:
                action = self.env["ir.actions.actions"]._for_xml_id('account_tax_settlement.action_account_tax_move_line')
                # action['domain'] = self._get_tax_settlement_lines_domain()
                action['domain'] = (
                    self._get_tax_settlement_lines_domain_by_tags())
                return action
            elif accounts_balance:
                action = self.env["ir.actions.actions"]._for_xml_id('account_ux.action_move_line_analisis')
                # action['domain'] = self._get_tax_settlement_lines_domain()
                action['domain'] = (
                    self._get_tax_settlement_lines_domain_by_tags_accounts())
                action['context'] = {'search_default_account': 1}
                return action
            # TODO revisar
            # elif open_report and self.settlement_financial_report_id:
            #     action = self.env['ir.actions.client'].search([
            #         ('name', '=',
            #             self.settlement_financial_report_id.get_report_name()),
            #         ('tag', '=', 'account_report')], limit=1)
            #     return action.sudo().read()[0]
            elif debt_balance and self.settlement_partner_id:
                action = self.settlement_partner_id.open_partner_ledger()
                ctx = self._context.copy()
                ctx.update({
                    'search_default_partner_id': self.settlement_partner_id.id,
                    'model': 'account.partner.ledger'
                })
                action['context'] = ctx
                return action
        return super(AccountJournal, self).open_action()
