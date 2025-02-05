from odoo import _, api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.onchange("name", "l10n_ar_afip_code", "symbol")
    def onchange_currency_name(self):
        return {
            "warning": {
                "title": _("Warning"),
                "message": _(
                    "Cambiar el nombre de la moneda puede repercutir tanto en el servicio de la sincronización automática de tasa de cambio como en el servicio de la facturación electrónica."
                ),
            }
        }
