##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models

_SIRCIP_TAX_GROUP_NAME = "SIRCIP"


class L10nArPartnerTax(models.Model):
    _inherit = "l10n_ar.partner.tax"

    @api.constrains("partner_id", "tax_id", "from_date", "to_date")
    def _check_tax_group_overlap(self):
        # Several SIRCIP records per partner and period are allowed
        non_sircip = self.filtered(lambda r: r.tax_id.tax_group_id.name != _SIRCIP_TAX_GROUP_NAME)
        return super(L10nArPartnerTax, non_sircip)._check_tax_group_overlap()
