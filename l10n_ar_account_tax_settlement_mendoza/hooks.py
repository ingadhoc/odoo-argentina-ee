from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """ Loaded after installing the module. Configuramos impuesto de Retención IIBB Mendoza Aplicada para que tengan código python.
    Se crea registro de coincidencia de importación para importar archivo de actividades de mendoza para que se actualice en base a los códigos
    existentes. """
    env = api.Environment(cr, SUPERUSER_ID, {})
    ar_companies = env['res.company'].search([]).filtered(lambda x: x.country_code == 'AR')
    for company in ar_companies:
        ret_mendoza_aplicada_ext_id = 'l10n_ar_account_withholding.%s_ri_tax_retencion_iibb_za_aplicada' % (company.id)
        ret_mendoza_aplicada_tax = env.ref(ret_mendoza_aplicada_ext_id, False)
        if not ret_mendoza_aplicada_tax:
            continue
        ret_mendoza_aplicada_tax.withholding_type = 'code'
        ret_mendoza_aplicada_tax.withholding_python_compute = "\n# withholdable_base_amount\n# payment: account.payment.group object\n# partner: res.partner object (commercial partner of payment group)\n# withholding_tax: account.tax.withholding object\n\nmove_to_pay = payment.to_pay_move_line_ids.move_id\nactivities = move_to_pay.activities_mendoza_ids\nif activities:\n    activity_codes = activities.mapped('code')\n    partner_vat = move_to_pay.partner_id.l10n_ar_formatted_vat\n    actividades_con_riesgo, actividades_con_alicuota_cero = payment.company_id.process_mendoza_csv_file(partner_vat, activity_codes)\n    menor_alicuota = activities.menor_alicuota(actividades_con_alicuota_cero)\n\n    if menor_alicuota[0] in actividades_con_riesgo:\n           alicuota = menor_alicuota[1] * 2\n    else:\n           alicuota = menor_alicuota[1]\n    payment.write({'alicuota_mendoza': alicuota})\n    result = withholdable_base_amount * alicuota\nelse:\n    result = False\n        "
        _logger.info('Se establece código python en impuesto de Retención IIBB Mendoza Aplicada para la compañía %s' % (company.name))
    afip_activity_model_id = env['ir.model'].search([('name', '=', 'afip.activity')]).id

    # Se crea registro de coincidencia de importación para importar archivo de actividades de mendoza para que se actualice en base a los códigos existentes.
    coincidencia_de_importacion = env['base_import.match'].create({'model_id': afip_activity_model_id})
    afip_activity_code_field_id = env['ir.model.fields'].search([('name', '=', 'code'), ('model_id', '=', 'afip.activity')]).id
    env['base_import.match.field'].create({'field_id': afip_activity_code_field_id,
                                           'match_id': coincidencia_de_importacion.id,
                                           'model_id': afip_activity_model_id})
    _logger.info('Se crea registro de coincidencia de importación para importar archivo de actividades de mendoza para que se actualice en base a los códigos existentes.')
