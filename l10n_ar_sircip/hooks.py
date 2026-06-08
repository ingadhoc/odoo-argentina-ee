##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging

_logger = logging.getLogger(__name__)

# Definición de los impuestos SIRCIP a crear por empresa.
# Clave técnica → (nombre, porcentaje, es_default_no_inscripto)
SIRCIP_TAXES = [
    ("tax_sircip_base", "SIRCIP A 0.0", 0.0, False),
    ("tax_sircip_sobretasa", "SIRCIP Sobre Alícuota 1%", 1.0, False),
    ("tax_sircip_no_inscripto", "SIRCIP No Inscripto 2%", 2.0, True),
]


def l10n_ar_sircip_post_init_hook(env):
    """Crea datos por empresa al instalar el módulo:
    - Grupo de impuestos SIRCIP
    - Impuestos base SIRCIP
    - Posición fiscal "Percepción - SIRCIP"
    - Línea de posición fiscal vinculada al impuesto No Inscripto
    - Diario de liquidación "SIRCIP Aplicado"
    """
    ar_companies = env["res.company"].search([("chart_template", "in", ("ar_base", "ar_ri", "ar_ex"))])
    sircip_state = env.ref("l10n_ar_sircip.state_ar_sircip", raise_if_not_found=False)
    if not sircip_state:
        _logger.warning("l10n_ar_sircip: no se encontró la provincia ficticia SIRCIP.")
        return

    for company in ar_companies:
        _create_sircip_data_for_company(env, company, sircip_state)

    if ar_companies:
        _logger.info(
            "l10n_ar_sircip: datos SIRCIP creados para: %s",
            ", ".join(ar_companies.mapped("name")),
        )


def _create_sircip_data_for_company(env, company, sircip_state):
    """Crea o actualiza los datos SIRCIP para una empresa dada."""
    env_co = env.with_company(company)

    # 1. Grupo de impuestos
    tax_group = env_co["account.tax.group"].search([("name", "=", "SIRCIP"), ("company_id", "=", company.id)], limit=1)
    if not tax_group:
        tax_group = env_co["account.tax.group"].create(
            {
                "name": "SIRCIP",
                "company_id": company.id,
            }
        )
        env["ir.model.data"].create(
            {
                "name": "tax_group_sircip_%s" % company.id,
                "module": "l10n_ar_sircip",
                "model": "account.tax.group",
                "res_id": tax_group.id,
                "noupdate": True,
            }
        )

    # 2. Impuestos base
    taxes_by_key = {}
    for xml_key, name, amount, _is_default in SIRCIP_TAXES:
        tax = env_co["account.tax"].search(
            [
                ("name", "=", name),
                ("company_id", "=", company.id),
                ("type_tax_use", "=", "sale"),
            ],
            limit=1,
        )
        if not tax:
            tax = env_co["account.tax"].create(
                {
                    "name": name,
                    "amount": amount,
                    "amount_type": "percent",
                    "type_tax_use": "sale",
                    "tax_group_id": tax_group.id,
                    "l10n_ar_state_id": sircip_state.id,
                    "company_id": company.id,
                }
            )
            env["ir.model.data"].create(
                {
                    "name": "%s_%s" % (xml_key, company.id),
                    "module": "l10n_ar_sircip",
                    "model": "account.tax",
                    "res_id": tax.id,
                    "noupdate": True,
                }
            )
        taxes_by_key[xml_key] = tax

    default_tax = taxes_by_key.get("tax_sircip_no_inscripto")

    # 3. Posición fiscal "Percepción - SIRCIP"
    fiscal_pos = env_co["account.fiscal.position"].search(
        [("name", "=", "Percepción - SIRCIP"), ("company_id", "=", company.id)], limit=1
    )
    if not fiscal_pos:
        fiscal_pos = env_co["account.fiscal.position"].create(
            {
                "name": "Percepción - SIRCIP",
                "auto_apply": True,
                "sequence": 9999,
                "country_id": env.ref("base.ar").id,
                "company_id": company.id,
                "note": "Posición fiscal exclusiva para agentes de percepción del SIRCIP (Convenio Multilateral). No asignar provincias individuales — la detección es automática.",
            }
        )
        env["ir.model.data"].create(
            {
                "name": "fiscal_position_sircip_%s" % company.id,
                "module": "l10n_ar_sircip",
                "model": "account.fiscal.position",
                "res_id": fiscal_pos.id,
                "noupdate": True,
            }
        )

    # 4. Línea de posición fiscal con webservice=padron e impuesto No Inscripto
    if default_tax:
        existing_line = env_co["account.fiscal.position.l10n_ar_tax"].search(
            [
                ("fiscal_position_id", "=", fiscal_pos.id),
                ("tax_type", "=", "perception"),
                ("webservice", "=", "padron"),
            ],
            limit=1,
        )
        if not existing_line:
            env_co["account.fiscal.position.l10n_ar_tax"].create(
                {
                    "fiscal_position_id": fiscal_pos.id,
                    "default_tax_id": default_tax.id,
                    "tax_type": "perception",
                    "webservice": "padron",
                }
            )

    # 5. Diario de liquidación "SIRCIP Aplicado"
    existing_journal = env_co["account.journal"].search(
        [("code", "=", "SIRC"), ("company_id", "=", company.id)], limit=1
    )
    if not existing_journal:
        sircip_tag = env.ref("l10n_ar_ux.tag_ret_perc_iibb_aplicada", raise_if_not_found=False)
        partner_iibb = env.ref("l10n_ar.par_iibb_pagar", raise_if_not_found=False)
        account_id = "account.%s_ri_retencion_iibb_a_pagar" % company.id
        if env.ref(account_id, raise_if_not_found=False):
            env_co["account.journal"].create(
                {
                    "type": "general",
                    "name": "Liquidación SIRCIP Aplicado",
                    "code": "SIRC",
                    "tax_settlement": "allow_per_line",
                    "settlement_tax": "iibb_aplicado_sircip",
                    "settlement_partner_id": partner_iibb.id if partner_iibb else False,
                    "settlement_account_id": account_id,
                    "company_id": company.id,
                    "show_on_dashboard": False,
                    "settlement_account_tag_ids": [(4, sircip_tag.id)] if sircip_tag else [],
                }
            )
