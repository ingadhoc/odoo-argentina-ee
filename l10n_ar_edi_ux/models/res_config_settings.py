from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    arba_cit = fields.Char(related="company_id.arba_cit", readonly=False)
