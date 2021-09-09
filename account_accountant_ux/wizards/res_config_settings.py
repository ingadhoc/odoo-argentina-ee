from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_company_currency_on_followup = fields.Boolean(
        related='company_id.use_company_currency_on_followup',
        readonly=False,
    )
