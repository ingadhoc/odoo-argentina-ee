import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def _l10n_ar_get_afip_ws_currency_rate(self, client, auth, afip_ws="wsfe", date_rate=None):
        """Retrieve the currency exchange rate and date from AFIP web services."""
        if afip_ws != "wsmtxca":
            return super()._l10n_ar_get_afip_ws_currency_rate(client, auth, afip_ws, date_rate)
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
        auth = self.env["account.journal"]._wsmtxca_convert_auth(auth)
        req_data = {"codigoMoneda": self.l10n_ar_afip_code}
        if date_rate:
            req_data["fechaCotizacion"] = date_rate.strftime("%Y-%m-%d")
        response = client.service.consultarCotizacionMoneda(auth, **req_data)
        if response.arrayErrores:
            _logger.warning("Errors getting currency rate from WSMTXCA: %s", response.arrayErrores)
            return date_rate, False
        rate = float(response.cotizacionMoneda)
        # ARCA expects the date as %Y-%m-%d, but l10n_ar_edi parses the returned one with %Y%m%d.
        date = fields.Date.to_date(date_rate or getattr(response, "fechaCotizacion", False))
        if not date:
            raise UserError(_("ARCA did not return the date of the currency rate for %s.", self.name))
        return date.strftime("%Y%m%d"), rate
