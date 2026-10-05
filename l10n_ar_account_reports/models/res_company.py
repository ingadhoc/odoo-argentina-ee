##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields=allfields, attributes=attributes)
        vat = res.get("vat")
        if vat is not None and (not attributes or "help" in attributes):
            # Append to the native help instead of replacing it
            ar_help = self.env._("For Argentina: if the company is not subject to tax, leave the Tax ID empty.")
            vat["help"] = f"{vat['help']}\n\n{ar_help}" if vat.get("help") else ar_help
        return res
