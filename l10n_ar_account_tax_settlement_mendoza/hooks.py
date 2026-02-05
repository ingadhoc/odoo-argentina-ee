import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Loaded after installing the module. Configuramos impuesto de Retención IIBB Mendoza Aplicada para que tengan código python.
    Se crea registro de coincidencia de importación para importar archivo de actividades de mendoza para que se actualice en base a los códigos
    existentes."""
    # Crear registros de fiscal position para todas las compañías argentinas
    for company in env["res.company"].search([]).filtered(lambda x: x.country_code == "AR"):
        # Buscar la posición fiscal "Retenciones" de esta compañía --> esta se crea en la ul 1415 [RET18] Migración retenciones de  Ganancias
        fiscal_position = env["account.fiscal.position"].search(
            [("name", "=", "Retenciones"), ("company_id", "=", company.id)], limit=1
        )

        if not fiscal_position:
            # No se encontró la posición fiscal 'Retenciones' para la compañía
            continue

        tax_ext_id_option_a = "account.%s_ex_tax_withholding_iibb_mza_applied" % company.id
        tax_ext_id_option_b = "l10n_ar_tax.%s_ri_tax_retencion_iibb_za_aplicada" % company.id
        default_tax = env.ref(tax_ext_id_option_a, raise_if_not_found=False) or env.ref(
            tax_ext_id_option_b, raise_if_not_found=False
        )
        if not default_tax:
            _logger.warning(
                "No se encontró el impuesto %s ni %s para la compañía %s"
                % (tax_ext_id_option_a, tax_ext_id_option_b, company.name)
            )
            continue

        # Verificar si ya existe el registro para esta compañía
        existing_record = env["account.fiscal.position.l10n_ar_tax"].search(
            [
                ("fiscal_position_id", "=", fiscal_position.id),
                ("default_tax_id", "=", default_tax.id),
                ("tax_type", "=", "withholding"),
            ],
            limit=1,
        )

        if not existing_record:
            python_formula = """
# payment: account.payment object
# partner: res.partner object (commercial partner of payment)

move_to_pay = payment.to_pay_move_line_ids.move_id
activities = move_to_pay.activities_mendoza_ids
if move_to_pay and activities:
    activity_codes = activities.mapped('code')
    partner_vat = move_to_pay.partner_id.l10n_ar_formatted_vat
    actividades_con_riesgo, actividades_con_alicuota_cero = payment.company_id.process_mendoza_csv_file(partner_vat, activity_codes)
    menor_alicuota = activities.menor_alicuota(actividades_con_alicuota_cero)

    if menor_alicuota[0] in actividades_con_riesgo:
        aliquot = menor_alicuota[1] * 2
    else:
        aliquot = menor_alicuota[1]
else:
    aliquot = 0
"""
            env["account.fiscal.position.l10n_ar_tax"].create(
                {
                    "fiscal_position_id": fiscal_position.id,
                    "default_tax_id": default_tax.id,
                    "tax_type": "withholding",
                    "webservice": "python_formula",
                    "python_formula": python_formula,
                }
            )
            _logger.info("Se crea registro de fiscal position para IIBB Mendoza en la compañía %s" % (company.name))

    afip_activity_model_id = env["ir.model"].search([("name", "=", "afip.activity")]).id

    # Se crea registro de coincidencia de importación para importar archivo de actividades de mendoza para que se actualice en base a los códigos existentes.
    coincidencia_de_importacion = env["base_import.match"].create({"model_id": afip_activity_model_id})
    afip_activity_code_field_id = (
        env["ir.model.fields"].search([("name", "=", "code"), ("model_id", "=", "afip.activity")]).id
    )
    env["base_import.match.field"].create(
        {
            "field_id": afip_activity_code_field_id,
            "match_id": coincidencia_de_importacion.id,
            "model_id": afip_activity_model_id,
        }
    )
    _logger.info(
        "Se crea registro de coincidencia de importación para importar archivo de actividades de mendoza para que se actualice en base a los códigos existentes."
    )
