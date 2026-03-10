# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class L10nArAfipwsConnection(models.Model):
    _inherit = "l10n_ar.afipws.connection"

    @api.model
    def _l10n_ar_get_afip_ws_url(self, afip_ws, environment_type):
        """Extend to add wsmtxca webservice."""
        if afip_ws != "wsmtxca":
            return super()._l10n_ar_get_afip_ws_url(afip_ws, environment_type)

        ws_data = {
            "wsmtxca": {
                "production": "https://serviciosjava.afip.gob.ar/wsmtxca/services/MTXCAService?wsdl",
                "testing": "https://fwshomo.afip.gov.ar/wsmtxca/services/MTXCAService?wsdl",
            },
        }
        return ws_data.get(afip_ws, {}).get(environment_type)
