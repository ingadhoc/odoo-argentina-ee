##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ar_sircip_agent = fields.Boolean(related="company_id.l10n_ar_sircip_agent", readonly=False)
    l10n_ar_sircip_account_id = fields.Many2one(related="company_id.l10n_ar_sircip_account_id", readonly=False)

    def set_values(self):
        super().set_values()
        # Saving with the option on completes new companies and new fiscal positions
        self.company_id._l10n_ar_sircip_setup()
