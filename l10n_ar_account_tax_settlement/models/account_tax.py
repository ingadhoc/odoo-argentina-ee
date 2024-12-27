from odoo import models, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'

    porcentaje_exclusion = fields.Float(string='Porcentaje de exclusión')
