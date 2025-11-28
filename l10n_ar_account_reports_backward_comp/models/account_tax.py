from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    is_backward_tax = fields.Boolean()
