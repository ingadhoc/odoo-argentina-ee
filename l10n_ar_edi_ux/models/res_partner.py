from odoo import models, fields, _
from odoo.exceptions import UserError
from odoo.tools.zeep.helpers import serialize_object
import logging
_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def button_update_partner_data_from_afip(self):
        self.ensure_one()
        wiz = self.env['res.partner.update.from.padron.wizard'].with_context(
            active_ids=self.ids, active_model=self._name).create({})
        wiz.change_partner()
        action = self.env["ir.actions.actions"]._for_xml_id('l10n_ar_edi_ux.action_partner_update')
        action['res_id'] = wiz.id
        return action

    def update_constancia_from_padron_afip(self):
        """ Este método descargaba la constancia en PDF desde afip pero dejó de estar disponible. Lo dejamos como
        recordatorio para implementar algo similar.
        TODO implementar o borrar
        """
        self.ensure_one()
        return True

    def _clean_response_obj(self, xml_tag, default_replace={}):
        """
        Este método procesa el response que nos devuelve afip para reemplazar los valores `None` por un valor predeterminado
        basado en el tipo de dato especificado. Si el response en sí es `None` o está vacío,
        lo reemplaza completamente con el valor indicado en el parámetro `type_replace`.

        El mapeo de tipos de datos y sus valores predeterminados se define en la variable interna `replace_values`.

        :param xml_tag: El respopnse o valor que se debe procesar.
                        Si está vacío o es `None`, se reemplaza completamente por `type_replace`.
        :param type_replace: Valor que se usará como reemplazo global si el diccionario está vacío o es `None`.
        :return: Diccionario modificado con los valores `None` reemplazados según el tipo especificado.
        """
        res = {}
        replace_values = {
            'datosGenerales': {},
            'caracterizacion': [],
            'domicilioFiscal': {},
            'codPostal': '',
            'descripcionProvincia': '',
            'direccion': '',
            'idProvincia': '',
            'localidad': '',
            'tipoDomicilio': '',
            'datoAdicional': '',
            'tipoDatoAdicional': '',
            'esSucesion': '',
            'estadoClave': '',
            'apellido': '',
            'dependencia': '',
            'nombre': '',
            'razonSocial': '',
            'tipoClave': '',
            'tipoPersona': '',
            'datosMonotributo': {},
            'datosRegimenGeneral': {},
            'actividad': [],
            'impuesto': [],
            'regimen': [],
            'errorConstancia': '',
            'errorMonotributo': '',
            'errorRegimenGeneral': '',
            'descripcionActividad': '',
            'descripcionImpuesto': '',
            'descripcionRegimen': '',
            'tipoRegimen': '',
            'metadata': {},
            'servidor': '',
        }

        # Si el diccionario es None o vacío, lo reemplazamos por el valor dado en type_replace
        if not xml_tag:
            return default_replace

        # Si el diccionario tiene valores, recorremos y reemplazamos los valores None
        # Si el valor en si es un diccionario lo limpiamops tambien
        if isinstance(xml_tag, dict):  # Procesar si es un diccionario
            cleaned = {}
            for key, value in xml_tag.items():
                type_replace = replace_values.get(key, default_replace)
                if isinstance(value, dict):
                    cleaned[key] = self._clean_response_obj(value, default_replace=type_replace)
                elif isinstance(value, list):
                    cleaned[key] = [
                        self._clean_response_obj(item, default_replace=type_replace) if isinstance(item, (dict, list)) else (type_replace if item is None else item)
                        for item in value
                    ]
                else:
                    cleaned[key] = type_replace if value is None else value
            return cleaned

    def get_data_from_padron_afip(self):
        self.ensure_one()
        vat = self.ensure_vat()

        # if there is certificate for current company use that one, if not use the company with first certificate found
        today = fields.Date.context_today(self.with_context(tz='America/Argentina/Buenos_Aires'))
        company = self.env.company if self.env.company.sudo().l10n_ar_afip_ws_crt and self.env.company.sudo().l10n_ar_crt_exp_date > today else self.env['res.company'].search(
            [('l10n_ar_afip_ws_crt', '!=', False), ('l10n_ar_crt_exp_date', '>', today)], limit=1)
        if not company:
            raise UserError(_('Please configure an AFIP Certificate in order to continue'))
        client, auth = company._l10n_ar_get_connection('ws_sr_constancia_inscripcion')._get_client()

        error_msg = _(
            'No pudimos actualizar desde padron afip al partner %s (%s).\nRecomendamos verificar manualmente en la'
            ' página de AFIP.\nObtuvimos este error:\n%s')

        errors = []
        values = {}
        try:
            res = client.service.getPersona(
                sign=auth.get('Sign'), token=auth.get('Token'), cuitRepresentada=auth.get('Cuit'), idPersona=vat)

            if res.errorConstancia:
                errors.append(res.errorConstancia)
            if res.errorMonotributo:
                errors.append(res.errorMonotributo)
            if res.errorRegimenGeneral:
                errors.append(res.errorRegimenGeneral)
        except Exception as e:
            raise UserError(error_msg % (self.name, vat, e))

        if errors:
            raise UserError(error_msg % (self.name, vat, errors))

        # Serializamos una sola vez
        res = serialize_object(res, dict)
        res = self._clean_response_obj(res)

        data = res.get('datosGenerales')

        if not data:
            raise UserError(error_msg % (self.name, vat, res))

        denominacion = data.get("razonSocial", "") or ", ".join([data.get("apellido", ""), data.get("nombre", "")])
        if not denominacion or denominacion == ', ':
            raise UserError(error_msg % (self.name, vat, 'La afip no devolvió nombre'))

        domicilio = data.get("domicilioFiscal")
        data_mt = res.get('datosMonotributo')
        data_rg = res.get('datosRegimenGeneral')

        impuestos = [imp["idImpuesto"]
                     for imp in data_mt.get("impuesto", []) + data_rg.get("impuesto", [])
                     if data.get('estadoClave') == 'ACTIVO']

        data_mt_actividades = data_mt.get("actividadMonotributista", []) or []
        if isinstance(data_mt_actividades, (dict,)):
            data_mt_actividades = [data_mt_actividades]

        actividades = [str(act["idActividad"])
                       for act in data_rg.get("actividad", []) + data_mt_actividades]

        def check_activity(data_rg, data_mt):
            res = []
            new_activity = {}
            afip_activities = data_rg.get("actividad", []) + ([data_mt.get("actividadMonotributista", [])] if data_mt else [])
            actividades = self.env['afip.activity'].sudo()
            activity_codes = actividades.search([]).mapped('code')
            for act in afip_activities:
                if act and str(act.get('idActividad')) not in activity_codes:
                    new_activity.update({
                        'code': act.get('idActividad'),
                        'name': act.get('descripcionActividad')
                    })
                    activity = actividades.create(new_activity)
                    res.append(activity)
                else:
                    res.append(act)
            return res
        check_activity(data_rg, data_mt)

        def check_taxes(data_mt, data_rg):
            res = []
            new_tax = {}
            afip_taxes = data_mt.get("impuesto", []) + data_rg.get("impuesto", [])
            taxes = self.env['afip.tax'].sudo()
            tax_codes = taxes.search([]).mapped('code')
            for imp in afip_taxes:
                if imp and str(imp.get('idImpuesto')) not in tax_codes:
                    new_tax.update({
                        'code': imp.get('idImpuesto'),
                        'name': imp.get('descripcionImpuesto')
                    })
                    tax = taxes.create(new_tax)
                    res.append(tax)
                else:
                    res.append(imp)
            return res
        check_taxes(data_mt, data_rg)

        cat_mt = data_mt.get("categoriaMonotributo", {})
        monotributo = "S" if cat_mt else "N"
        map_pronvincias = {
            0: 'CIUDAD AUTONOMA BUENOS AIRES', 1: 'BUENOS AIRES',
            2: 'CATAMARCA', 3: 'CORDOBA', 4: 'CORRIENTES', 5: 'ENTRE RIOS', 6: 'JUJUY',
            7: 'MENDOZA', 8: 'LA RIOJA', 9: 'SALTA', 10: 'SAN JUAN', 11: 'SAN LUIS',
            12: 'SANTA FE', 13: 'SANTIAGO DEL ESTERO', 14: 'TUCUMAN', 16: 'CHACO',
            17: 'CHUBUT', 18: 'FORMOSA', 19: 'MISIONES', 20: 'NEUQUEN', 21: 'LA PAMPA',
            22: 'RIO NEGRO', 23: 'SANTA CRUZ', 24: 'TIERRA DEL FUEGO'}
        provincia = map_pronvincias.get(domicilio.get("idProvincia"), "")

        if 32 in impuestos:
            imp_iva = "EX"
        elif 33 in impuestos:
            imp_iva = "NI"
        elif 34 in impuestos:
            imp_iva = "NA"
        else:
            imp_iva = "AC" if 30 in impuestos else "NI"

        values.update({
            'name': denominacion,
            'estado_padron': data.get('estadoClave'),
            'street': domicilio.get("direccion", domicilio.get("localidad", provincia)),
            'city': domicilio.get("localidad"),
            'zip': domicilio.get("codPostal", ""),
            'actividades_padron': self.actividades_padron.search([('code', 'in', actividades)]).ids,
            'impuestos_padron': self.impuestos_padron.search([('code', 'in', impuestos)]).ids,
            'imp_iva_padron': imp_iva,
            'monotributo_padron': monotributo,
            'actividad_monotributo_padron': cat_mt.get("descripcionCategoria") if cat_mt else "",
            'empleador_padron': True if 301 in impuestos else False,
            'integrante_soc_padron': "",
            'last_update_padron': fields.Date.today(),
        })

        ganancias_inscripto = [10, 11]
        ganancias_exento = [12]
        if set(ganancias_inscripto) & set(impuestos):
            values['imp_ganancias_padron'] = 'AC'
        elif set(ganancias_exento) & set(impuestos):
            values['imp_ganancias_padron'] = 'EX'
        elif monotributo == 'S':
            values['imp_ganancias_padron'] = 'NC'
        else:
            _logger.info("We couldn't get impuesto a las ganancias from padron, you must set it manually")

        if provincia:
            # depending on the database, caba can have one of this codes
            caba_codes = ['C', 'CABA', 'ABA']
            # if not localidad then it should be CABA.
            if not domicilio.get("localidad"):
                state = self.env['res.country.state'].search([
                    ('code', 'in', caba_codes), ('country_id.code', '=', 'AR')], limit=1)
            # If localidad cant be caba
            else:
                state = self.env['res.country.state'].search([
                    ('name', 'ilike', provincia), ('code', 'not in', caba_codes), ('country_id.code', '=', 'AR')],
                    limit=1)
            if state:
                values['state_id'] = state.id

        if imp_iva == 'NI' and monotributo == 'S':
            values['l10n_ar_afip_responsibility_type_id'] = self.env.ref('l10n_ar.res_RM').id
        elif imp_iva == 'AC':
            values['l10n_ar_afip_responsibility_type_id'] = self.env.ref('l10n_ar.res_IVARI').id
        elif imp_iva == 'EX':
            values['l10n_ar_afip_responsibility_type_id'] = self.env.ref('l10n_ar.res_IVAE').id
        else:
            _logger.info("We couldn't infer the AFIP responsability from padron, you must set it manually.")

        return values
