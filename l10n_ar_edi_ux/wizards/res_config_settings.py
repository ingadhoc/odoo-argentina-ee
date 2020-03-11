from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    arba_cit = fields.Char(related='company_id.arba_cit', readonly=False)

    def refresh_taxes_from_padron(self):
        self.refresh_from_padron("impuestos")

    def refresh_concepts_from_padron(self):
        self.refresh_from_padron("conceptos")

    def refresh_activities_from_padron(self):
        self.refresh_from_padron("actividades")

    @api.model
    def refresh_from_padron(self, resource_type):
        """ resource_type puede ser "impuestos", "conceptos", "actividades" """
        data = {'impuestos': 'afip.tax', 'actividades': 'afip.activity', 'conceptos': 'afip.concept'}
        resource_name = resource_type.capitalize().replace('tos', 'to').replace('des', 'd')

        model = data.get(resource_type)
        if not model:
            raise UserError(_('Resource Type %s not implemented!') % (resource_type))

        url = "https://soa.afip.gob.ar/parametros/v1/%s/" % resource_type
        res = requests.get(url=url)
        data = res.json().get('data')
        if res.status_code != 200:
            raise UserError(_('Error getting %s params from AFIP!') % resource_type)

        codes = []
        for item in data:
            code = item.get("id" + resource_name)
            values = {'code': code,
                      'name': item.get("desc" + resource_name),
                      'active': True}
            record = self.env[model].search([('code', '=', code)], limit=1)
            codes.append(code)
            if record:
                record.write(values)
            else:
                record.create(values)

        # deactivate the ones that are not in afip
        self.env[model].search([('code', 'not in', codes)]).write({'active': False})
