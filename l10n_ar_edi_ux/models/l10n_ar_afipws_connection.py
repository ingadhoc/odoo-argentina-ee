# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.addons.l10n_ar_edi.models import l10n_ar_afipws_connection as edi_connection
from odoo.tools.zeep import Client
from zeep.cache import InMemoryCache

WSDL_CACHE_TTL_PARAM = "l10n_ar_edi_ux.wsdl_cache_ttl"
DEFAULT_WSDL_CACHE_TTL = 300


class L10nArAfipwsConnection(models.Model):
    _inherit = "l10n_ar.afipws.connection"

    def _get_l10n_ar_afip_ws(self):
        """Return the list of values of the selection field."""
        res = super()._get_l10n_ar_afip_ws()
        return [
            ("ws_sr_constancia_inscripcion", _("Servicio de Consulta a Padrón Constancia de Inscripción (ex A5)"))
        ] + res

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
