# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api, _


class L10nArAfipwsConnection(models.Model):

    _inherit = "l10n_ar.afipws.connection"

    def _get_l10n_ar_afip_ws(self):
        """ Return the list of values of the selection field. """
        res = super()._get_l10n_ar_afip_ws()
        return [('ws_sr_padron_a5', _('Servicio de Consulta de Padrón Alcance 5'))] + res

    @api.model
    def _l10n_ar_get_afip_ws_url(self, afip_ws, environment_type):
        """ extend to add ws_sr_padron_a5 webservice """
        res = super()._l10n_ar_get_afip_ws_url(afip_ws, environment_type)
        if res:
            return res

        ws_data = {
            'ws_sr_padron_a5': {
                'production': 'https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl',
                'testing': 'https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl',
        }}
        return ws_data.get(afip_ws, {}).get(environment_type)
