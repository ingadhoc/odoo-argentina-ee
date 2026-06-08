##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    l10n_ar_is_sircip = fields.Boolean(
        string="Adherida a SIRCIP",
        help="Indica que la provincia está adherida al SIRCIP (Sistema de Recaudación del Control sobre Ingresos Brutos de Convenio Multilateral). Las facturas a clientes con domicilio de entrega en esta provincia pueden generar percepciones SIRCIP.",
    )
