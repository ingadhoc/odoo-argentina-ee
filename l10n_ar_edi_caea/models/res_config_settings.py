from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ar_contingency_mode = fields.Boolean(related='company_id.l10n_ar_contingency_mode', readonly=False)

    l10n_ar_last_contigency = fields.Datetime(related="company_id.l10n_ar_last_contigency")
