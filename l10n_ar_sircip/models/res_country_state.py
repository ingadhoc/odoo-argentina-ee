##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


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
