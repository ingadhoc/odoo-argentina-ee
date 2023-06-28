from odoo import models, fields


class AccountMovetLine(models.Model):

    _inherit = 'account.move.line'

    filter_amount = fields.Float(compute="compute_filter_amout", search='_search_filter_amount')
    
    def compute_filter_amout(self):
        self.filter_amount = False

    def _search_filter_amount(self, operator, value):
        res = []
        if self.env.context.get('default_st_line_id'):
            amount = self.env['account.bank.statement.line'].browse(self.env.context.get('default_st_line_id'))['amount'] 
            if value != 0 and operator == '=':
                base_amount = ((100 - value)/100) * amount
                top_amount = ((100 + value)/100) * amount
                res.append(('amount_residual', '>',  base_amount))
                res.append(('amount_residual', '<',  top_amount))
            else:
                amount = ((100 - value)/100) * amount
                res.append(('amount_residual', operator,  amount))
        return res
