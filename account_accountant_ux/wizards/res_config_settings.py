from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_company_currency_on_followup = fields.Boolean(
        related='company_id.use_company_currency_on_followup',
        readonly=False,
    )

    use_search_filter_amount = fields.Boolean(
        config_parameter='account_accountant_ux.use_search_filter_amount',
        readonly=False,
        )
