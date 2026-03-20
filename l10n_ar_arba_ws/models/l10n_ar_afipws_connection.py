# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

import requests
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class L10nArAfipwsConnection(models.Model):
    _inherit = "l10n_ar.afipws.connection"

    def _get_l10n_ar_afip_ws(self):
        # EXTEND l10n_ar_edi
        """Agregamos el webservice para conectarnos a ARBA y manejar DDJJ y RET"""
        return super()._get_l10n_ar_afip_ws() + [("A122R", self.env._("Withholding Webservice (A122R)"))]

    @api.model
    def _l10n_ar_get_afip_ws_url(self, afip_ws, environment_type):
        # EXTEND l10n_ar_edi
        """Agregamos las URL para conectarnos al ws A122R"""
        if afip_ws == "A122R":
            ws_data = {
                "production": "https://app.arba.gov.ar/a122rSrv/api/external",
                "testing": "https://app2.test.arba.gov.ar/a122rSrv/api/external",
            }
            return ws_data.get(environment_type)

        return super()._l10n_ar_get_afip_ws_url(afip_ws, environment_type)

    def _l10n_ar_get_token_data(self, company, afip_ws):
        """Extendemos para agrega la logica de obtener el token de ARBA, que es
        diferente a la de AFIP, no se obtiene por wsdl sino por una URL y
        con un payload distinto"""
        if afip_ws == "A122R":
            return self._l10n_ar_get_token_data_arba(company, afip_ws)
        return super()._l10n_ar_get_token_data(company, afip_ws)

    def _l10n_ar_get_token_data_arba(self, company, afip_ws):
        """Logica de obtener el token de ARBA
        NOTA: Ojo el token dura 5 minutos

        Ejemplo del response del token de ARBA:
        {
            "access_token": "eyJhbGci0iJSUzI1NiIsInR5cCIg0iAisldUIiwia2lkIiA6ICJyaUhLNmwxZXZtYjBVeF9GaFMxM3JSQUDSNWozemE5V2dRX1
            "expires_in": 300,
            "refresh_expires_in": 1800,
            "refresh_token": "eyJhbGci0iJIUzUxMiIsInR5cCIg0iAiSldUIiwia2lkIiA6ICJjODJZZDJLNY05Yzg4LTRhYjUtODlhNS02YWVjNDLhMzQwNI
            "token_type": "Bearer",
            "not-before-policy": 0,
            "session_state": "6682bdc3-6953-46b2-88d7-351c18a19576",
        }
        """
        generation_time = fields.Datetime.now()
        environment_type = company.l10n_ar_arba_env

        if environment_type == "demo":
            return {
                "uniqueid": "FAKE_TOKEN_FOR_DEMO_ENVIRONMENT",
                "generation_time": generation_time,
                "expiration_time": generation_time + relativedelta(seconds=900000),
                "token": "FAKE_TOKEN_FOR_DEMO_ENVIRONMENT",
            }

        ws_url = {
            "production": "https://idp.arba.gov.ar/realms/ARBA/protocol/openid-connect/token",
            "testing": "https://idp.test.arba.gov.ar/realms/ARBA/protocol/openid-connect/token",
        }
        url = ws_url.get(environment_type)

        user = company.partner_id.ensure_vat()
        password = company.arba_cit
        client_secret = company.l10n_ar_arba_client_secret
        client_id = company.l10n_ar_arba_client_id

        error = False
        try:
            _logger.info("Connect to ARBA to get token: %s %s", afip_ws, company.name)
            payload = (
                f"client_id={client_id}&username={user}&password={password}&client_secret={client_secret}&"
                "grant_type=password&scope=arba-profile%20arba-roles%20openid"
            )
            # "Cookie": "arbalb=1477775370.47873.0000"  # es necesario? es variable?
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            generation_time = fields.Datetime.now()
            response = requests.request("POST", url, headers=headers, data=payload, timeout=(10, 60))
            # TODO: Como implementar un transport con request
            if response.status_code != 200:
                error = f"{response.status_code} - {response.text}"

        except Exception as exp:
            error = str(exp)

        if error:
            return self._l10n_ar_process_connection_error(error, environment_type, afip_ws)

        response = response.json()
        return {
            "token": response.get("access_token"),
            "expiration_time": generation_time + relativedelta(seconds=response.get("expires_in")),
            "generation_time": generation_time,
            "uniqueid": response.get("refresh_token"),
            "sign": response.get("session_state"),
        }
