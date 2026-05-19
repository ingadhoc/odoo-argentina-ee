from odoo import api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _search_by_name(self, currency_name):
        return self.search([("name", "=", currency_name)])
