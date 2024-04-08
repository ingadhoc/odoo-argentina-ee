import logging
_logger = logging.getLogger(__name__)


def l10n_ar_account_tax_settlement_post_init_hook(env):
    """ Al instalar este módulo (l10n_ar_account_tax_settlement), en caso de que existan compañías responsable inscripto argentinas y con plan de cuentas ya establecido entonces a los impuestos de retenciones de ganancias e iva les agregamos el código de impuesto correspondiente. También agregamos etiquetas a las repartition lines de impuestos de retenciones. """

    # verificamos que la compañía sea argentina, responsable inscripto y tenga plan de cuentas instalado
    companies = env['res.company'].search([('l10n_ar_afip_responsibility_type_id.code', '=', '1'), ('chart_template', '=', 'ar_ri')])
    for company in companies:
        # Retenciones aplicadas de ganancias
        impuesto_ret_gcias_aplic = env.ref("account.%s_%s" % (company.id, 'ri_tax_withholding_ganancias_applied'))
        if impuesto_ret_gcias_aplic:
            impuesto_ret_gcias_aplic.codigo_impuesto = '01'
        # Retenciones aplicadas de iva
        impuesto_ret_iva_aplic = env.ref("account.%s_%s" % (company.id, 'ri_tax_withholding_vat_applied'))
        if impuesto_ret_iva_aplic:
            impuesto_ret_iva_aplic.codigo_impuesto = '02'
        # Agregamos impuestos etiquetas de impuestos
        env['account.chart.template']._add_wh_taxes(company)

    # Dejamos registro en los logs de las compañías en las cuales se estableció el código de impuesto
    if companies:
        _logger.info("Se agregaron los códigos de impuestos correspondientes para retenciones de ganancias aplicadas y retenciones de iva aplicadas y las etiquetas de impuestos para compañías %s." % ', '.join(companies.mapped('name')))

