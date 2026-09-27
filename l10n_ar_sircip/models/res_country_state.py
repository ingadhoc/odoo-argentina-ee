##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models
from odoo.osv import expression


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    l10n_ar_is_sircip = fields.Boolean(
        string="Adhered to SIRCIP",
        help=(
            "Indicates that the province adheres to the SIRCIP (Sistema de "
            "Recaudación del Control sobre Ingresos Brutos de Convenio "
            "Multilateral). Invoices to customers with a delivery address in "
            "this province may generate SIRCIP perceptions."
        ),
    )

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Offer the SIRCIP pseudo-province only where it is used: the padron and the tax."""
        sircip_state = self.env.ref("l10n_ar_sircip.state_ar_sircip", raise_if_not_found=False)
        if sircip_state and not self.env.context.get("l10n_ar_sircip_show_state"):
            args = expression.AND([args or [], [("id", "!=", sircip_state.id)]])
        return super().name_search(name, args, operator, limit)
