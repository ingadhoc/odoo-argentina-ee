from odoo import fields, models


class AccountArVatLine(models.Model):
    _inherit = "account.ar.vat.line"

    account_id = fields.Many2one("account.account", related="journal_id.default_account_id", readonly=True, store=True)
