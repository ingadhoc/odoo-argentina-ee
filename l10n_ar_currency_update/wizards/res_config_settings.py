##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    rate_perc = fields.Float(related="company_id.rate_perc", readonly=False)
    rate_surcharge = fields.Float(related="company_id.rate_surcharge", readonly=False)

    @api.onchange("rate_perc")
    def _change_rate_perc(self):
        _logger.log(
            25,
            "debug_l10n_ar_currency_update - rate_perc changed from '%s' to '%s' for company '%s' by user '%s'",
            self._origin.rate_perc,
            self.rate_perc,
            self.company_id.name,
            self.env.user.name,
        )

    @api.onchange("rate_surcharge")
    def _change_rate_surcharge(self):
        _logger.log(
            25,
            "debug_l10n_ar_currency_update - rate_surcharge changed from '%s' to '%s' for company '%s' by user '%s'",
            self._origin.rate_surcharge,
            self.rate_surcharge,
            self.company_id.name,
            self.env.user.name,
        )
