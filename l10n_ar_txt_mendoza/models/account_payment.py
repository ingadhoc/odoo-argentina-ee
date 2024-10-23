from odoo import models, fields, api


class AccountPayment(models.Model):

    _inherit = "account.payment"

    alicuota_mendoza = fields.Float(store=True, readonly=True)
