from odoo import models, api, fields
from odoo.exceptions import UserError
from odoo.osv import expression

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    credit = fields.Monetary(search='_credit_search')
    debit = fields.Monetary(search='_debit_search')

    def open_mass_partner_ledger(self):
        selected_partner_ids = self.env.context.get('active_ids')
        if len(selected_partner_ids) < 1000:
        
            action = self.env["ir.actions.actions"]._for_xml_id("account_reports.action_account_report_partner_ledger")
            action['params'] = {

                'options': {'partner_ids': selected_partner_ids},
                'ignore_session': 'both',
            }
            return action
        else:
            raise UserError('Se deben seleccionar menos de 1000 contactos')
        
    @api.model
    def _credit_search(self, operator, operand):
        if len(self.env.companies) > 1:
            domain = []
            for company in self.env.companies:
                cond = self.with_company(company)._asset_difference_search(
                    account_type='asset_receivable',
                    operator=operator,
                    operand=operand
                )
                if cond:
                    domain = expression.OR([domain, cond])

            if not domain:
                return [('id', '=', 0)]
                
            return domain
        else:
            return super()._credit_search(operator, operand)

    @api.model
    def _debit_search(self, operator, operand):
        if len(self.env.companies) > 1:
            domain = []
            for company in self.env.companies:
                cond = self.with_company(company)._asset_difference_search(
                    account_type='liability_payable',
                    operator=operator,
                    operand=operand
                )
                if cond:
                    domain = expression.OR([domain, cond])

            if not domain:
                return [('id', '=', 0)]

            return domain
        else:
            return super()._debit_search(operator, operand)
