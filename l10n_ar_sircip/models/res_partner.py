##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("state_id")
    def _check_l10n_ar_sircip_state(self):
        sircip_state = self.env.ref("l10n_ar_sircip.state_ar_sircip", raise_if_not_found=False)
        if sircip_state and self.filtered(lambda x: x.state_id == sircip_state):
            raise ValidationError(
                self.env._("SIRCIP is not a province: it only identifies the SIRCIP padron and taxes.")
            )
