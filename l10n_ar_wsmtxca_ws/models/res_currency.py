import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def _l10n_ar_get_afip_ws_currency_rate(self, afip_ws="wsfe", date_rate=None):
        """Retrieve the currency exchange rate and date from AFIP web services."""
        if afip_ws != "wsmtxca":
            return super()._l10n_ar_get_afip_ws_currency_rate(afip_ws, date_rate)
        self.ensure_one()
        if not self.l10n_ar_afip_code:
            raise UserError(
                _(
                    "No AFIP code for currency %s. Please configure the AFIP code consulting information in AFIP page",
                    self.name,
                )
            )
        if self.l10n_ar_afip_code == "PES":
            raise UserError(_("No rate for ARS (is the base currency for AFIP)"))
        connection = self.env.company._l10n_ar_get_connection(afip_ws)
        client, auth = connection._get_client()
        auth = self.env["account.journal"]._wsmtxca_convert_auth(auth)
        req_data = {"codigoMoneda": self.l10n_ar_afip_code}
        if date_rate:
            req_data["fechaCotizacion"] = date_rate.strftime("%Y-%m-%d")
        response = client.service.consultarCotizacionMoneda(auth, **req_data)
        if response.arrayErrores:
            _logger.warning("Errors getting currency rate from WSMTXCA: %s", response.arrayErrores)
            return date_rate, False
        rate = float(response.cotizacionMoneda)
        date = date_rate.strftime("%Y-%m-%d") if date_rate else getattr(response, "fechaCotizacion", False)
        return date, rate
