# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, models
from odoo.addons.l10n_ar_edi.models import l10n_ar_afipws_connection as edi_connection
from odoo.exceptions import UserError
from odoo.tools.zeep import Client
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    HTTPError,
    Timeout,
)
from urllib3.exceptions import MaxRetryError
from zeep.cache import InMemoryCache
from zeep.exceptions import TransportError

_logger = logging.getLogger(__name__)

WSDL_CACHE_TTL_PARAM = "l10n_ar_edi_ux.wsdl_cache_ttl"
DEFAULT_WSDL_CACHE_TTL = 300

ARCA_UNAVAILABLE = "unavailable"
ARCA_UNCONFIRMED = "unconfirmed"


class L10nArAfipwsConnection(models.Model):
    _inherit = "l10n_ar.afipws.connection"

    def _get_l10n_ar_afip_ws(self):
        """Return the list of values of the selection field."""
        res = super()._get_l10n_ar_afip_ws()
        return [("ws_sr_constancia_inscripcion", _("ARCA Registration Certificate Inquiry Service (ex A5)"))] + res

    @api.model
    def _l10n_ar_get_afip_ws_url(self, afip_ws, environment_type):
        """extend to add ws_sr_constancia_inscripcion webservice"""
        res = super()._l10n_ar_get_afip_ws_url(afip_ws, environment_type)
        if res:
            return res

        ws_data = {
            "ws_sr_constancia_inscripcion": {
                "production": "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl",
                "testing": "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl",
            }
        }
        return ws_data.get(afip_ws, {}).get(environment_type)

    def _l10n_ar_get_token_data(self, company, afip_ws):
        # EXTEND l10n_ar_edi
        """We want to check first if the certificate match with the company CUIT before trying to get token data"""
        company._check_match_between_certificate_and_company()
        return super()._l10n_ar_get_token_data(company, afip_ws)

    def _get_client(self, return_transport=False):
        """Cachea el WSDL de AFIP en lugar de bajarlo en cada llamada.

        Upstream arma el transporte con `cache=None`, asi que zeep vuelve a descargar el
        WSDL en cada cliente; como esto se llama por factura, son ~0,65 s por comprobante.
        El TTL sale del parametro `l10n_ar_edi_ux.wsdl_cache_ttl`; en cero delega en `super()`.
        """
        ttl = int(self.env["ir.config_parameter"].sudo().get_param(WSDL_CACHE_TTL_PARAM, DEFAULT_WSDL_CACHE_TTL))
        if ttl <= 0:
            return super()._get_client(return_transport=return_transport)

        wsdl = self._l10n_ar_get_afip_ws_url(self.l10n_ar_afip_ws, self.type)
        auth = {"Token": self.token, "Sign": self.sign, "Cuit": self.company_id.partner_id.ensure_vat()}
        try:
            transport = edi_connection.ARTransport(operation_timeout=60, timeout=60, cache=InMemoryCache(timeout=ttl))
            client = Client(wsdl, transport=transport)
        except Exception as error:
            self._l10n_ar_process_connection_error(error, self.type, self.l10n_ar_afip_ws)
        if return_transport:
            return client, auth, edi_connection.SimpleTransport(transport)
        return client, auth

    @api.model
    def _l10n_ar_arca_error_kind(self, error, request_sent=False):
        """Classify a transport failure while talking to ARCA.

        Returns ARCA_UNAVAILABLE when the request did not reach ARCA, ARCA_UNCONFIRMED when it was sent and
        ARCA may have processed it, and None when the error is not a transport failure.
        """
        status = None
        if isinstance(error, HTTPError) and error.response is not None:
            status = error.response.status_code
        elif isinstance(error, TransportError):
            status = error.status_code
        if status is not None:
            return ARCA_UNAVAILABLE if status >= 500 else None
        if isinstance(error, Timeout | RequestsConnectionError):
            # MaxRetryError means the connection itself failed, so nothing was sent
            connect_failed = isinstance(error, RequestsConnectionError) and isinstance(
                error.args[0] if error.args else None, MaxRetryError
            )
            return ARCA_UNAVAILABLE if connect_failed or not request_sent else ARCA_UNCONFIRMED
        return None

    @api.model
    def _l10n_ar_arca_error_message(self, kind):
        if kind == ARCA_UNCONFIRMED:
            return _(
                "ARCA did not confirm the authorization\n\n"
                "The communication with ARCA was interrupted while the document was being validated and we could "
                "not confirm whether it was authorized.\n\n"
                "Before validating it again, check in ARCA what the last issued document was for this document "
                "type and point of sale.\n"
                "- If ARCA already issued this document, do not validate it again: register in Odoo the "
                'authorization reported by ARCA, following the manual "Error 10016 de ARCA".\n'
                "- If it did not, validate it again."
            )
        return _(
            "ARCA is not available\n\n"
            "The ARCA electronic invoicing service is not responding at the moment, so the document could not be "
            "validated. This is not an error in the document or in your configuration.\n\n"
            "Try validating it again later."
        )

    @api.model
    def _l10n_ar_process_connection_error(self, error, env_type, afip_ws):
        # EXTEND l10n_ar_edi
        """Show a clear message when ARCA is down instead of the raw HTTP error and URL"""
        if self._l10n_ar_arca_error_kind(error):
            _logger.info("ARCA %s webservice unavailable: %r", afip_ws, error)
            raise UserError(self._l10n_ar_arca_error_message(ARCA_UNAVAILABLE)) from error
        return super()._l10n_ar_process_connection_error(error, env_type, afip_ws)
