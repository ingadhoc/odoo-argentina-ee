from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    porcentaje_exclusion = fields.Float(string="Porcentaje de exclusión")
