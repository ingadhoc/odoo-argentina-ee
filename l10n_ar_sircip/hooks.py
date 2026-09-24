##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging

from dateutil.relativedelta import relativedelta
from odoo import Command, fields

from .models.account_tax import (
    SIRCIP_RECORD_NOT_REGISTERED,
    SIRCIP_RECORD_PERCEPTION,
    SIRCIP_RECORD_SURCHARGE,
)

_logger = logging.getLogger(__name__)

# Plantillas por compañía: (clave del xmlid, nombre, alícuota, tipo de registro de la DDJJ, activa).
# De "Percepción SIRCIP" y de la sobretasa se crea una copia por alícuota y por provincia al facturar;
# "por no inscripto" es el impuesto por defecto de la línea de posición fiscal.
# Los nombres son la denominación que exige la Comisión Arbitral en la factura.
SIRCIP_TAXES = [
    ("tax_sircip_percepcion", "Percepción SIRCIP", 0.0, SIRCIP_RECORD_PERCEPTION, False),
    ("tax_sircip_no_inscripto", "Percepción SIRCIP por no inscripto", 2.0, SIRCIP_RECORD_NOT_REGISTERED, True),
    ("tax_sircip_sobretasa", "Percepción SIRCIP por falta de alta", 1.0, SIRCIP_RECORD_SURCHARGE, False),
]

# Código de tributo AFIP de las percepciones de IIBB, el que usan los grupos provinciales de l10n_ar
_AFIP_TRIBUTE_IIBB = "07"


def l10n_ar_sircip_post_init_hook(env):
    """Crea por empresa argentina: grupo de impuestos, cuenta, impuestos plantilla, la posición fiscal
    "Percepción - SIRCIP", la línea SIRCIP en las posiciones fiscales con percepciones y el diario de
    liquidación."""
    ar_companies = env["res.company"].search([("chart_template", "in", ("ar_base", "ar_ri", "ar_ex"))])
    sircip_state = env.ref("l10n_ar_sircip.state_ar_sircip")
    for company in ar_companies:
        _create_sircip_data_for_company(env, company, sircip_state)
    if env.ref("base.user_demo", raise_if_not_found=False):
        _setup_demo_sircip_padron_data(env)


def _xmlid(env, name, record):
    env["ir.model.data"].create(
        {"name": name, "module": "l10n_ar_sircip", "model": record._name, "res_id": record.id, "noupdate": True}
    )


def _get_or_create_account(env, company):
    """Cuenta de pasivo "Percepción IIBB SIRCIP aplicada", al lado de las percepciones provinciales del plan."""
    account = env.ref("l10n_ar_sircip.account_sircip_%s" % company.id, raise_if_not_found=False)
    if account:
        return account
    Account = env["account.account"].with_company(company)
    sibling = env.ref("account.%s_ri_percepcion_iibb_tf_aplicada" % company.id, raise_if_not_found=False)
    if not sibling:
        _logger.info("l10n_ar_sircip: %s sin cuenta de percepciones IIBB aplicadas del plan AR.", company.name)
        return Account
    account = Account.create(
        {
            "name": "Percepción IIBB SIRCIP aplicada",
            "code": Account._search_new_account_code(sibling.with_company(company).code),
            "account_type": sibling.account_type,
            "company_ids": [Command.link(company.id)],
        }
    )
    _xmlid(env, "account_sircip_%s" % company.id, account)
    return account


def _create_sircip_data_for_company(env, company, sircip_state):
    Tax = env["account.tax"].with_company(company)
    FiscalPos = env["account.fiscal.position"].with_company(company)
    FiscalPosLine = env["account.fiscal.position.l10n_ar_tax"].with_company(company)

    # 1. Grupo de impuestos
    tax_group = env.ref("l10n_ar_sircip.tax_group_sircip_%s" % company.id, raise_if_not_found=False)
    if not tax_group:
        tax_group = (
            env["account.tax.group"]
            .with_company(company)
            .create({"name": "SIRCIP", "company_id": company.id, "l10n_ar_tribute_afip_code": _AFIP_TRIBUTE_IIBB})
        )
        _xmlid(env, "tax_group_sircip_%s" % company.id, tax_group)

    # 2. Impuestos plantilla, con la cuenta y la etiqueta que usa el diario de liquidación
    account = _get_or_create_account(env, company)
    tag = env.ref("l10n_ar_sircip.tag_perc_iibb_sircip_aplicada")
    repartition = [
        Command.clear(),
        Command.create({"repartition_type": "base"}),
        Command.create({"repartition_type": "tax", "account_id": account.id, "tag_ids": [Command.set(tag.ids)]}),
    ]
    taxes = {}
    for key, name, amount, record_type, active in SIRCIP_TAXES:
        tax = env.ref("l10n_ar_sircip.%s_%s" % (key, company.id), raise_if_not_found=False)
        if not tax:
            tax = Tax.create(
                {
                    "name": name,
                    "amount": amount,
                    "amount_type": "percent",
                    "type_tax_use": "sale",
                    "tax_group_id": tax_group.id,
                    "l10n_ar_state_id": sircip_state.id,
                    "l10n_ar_sircip_record_type": record_type,
                    "company_id": company.id,
                    "active": active,
                    "invoice_repartition_line_ids": repartition,
                    "refund_repartition_line_ids": repartition,
                }
            )
            _xmlid(env, "%s_%s" % (key, company.id), tax)
        taxes[key] = tax
    default_tax = taxes["tax_sircip_no_inscripto"]
    sircip_line_vals = {"default_tax_id": default_tax.id, "tax_type": "perception", "webservice": "padron"}

    # 3. Posición fiscal "Percepción - SIRCIP": al final de las de percepción, para los clientes que no caen
    # en ninguna otra
    fiscal_pos = env.ref("l10n_ar_sircip.fiscal_position_sircip_%s" % company.id, raise_if_not_found=False)
    if not fiscal_pos:
        ivari = env.ref("l10n_ar.res_IVARI", raise_if_not_found=False)
        fiscal_pos = FiscalPos.create(
            {
                "name": "Percepción - SIRCIP",
                "auto_apply": True,
                "sequence": 9999,
                "country_id": env.ref("base.ar").id,
                "company_id": company.id,
                # Sin responsabilidad AFIP la posición no se autoselecciona en las facturas
                "l10n_ar_afip_responsibility_type_ids": [Command.set(ivari.ids)] if ivari else [],
                "l10n_ar_tax_ids": [Command.create(sircip_line_vals)],
            }
        )
        _xmlid(env, "fiscal_position_sircip_%s" % company.id, fiscal_pos)

    # 4. Línea SIRCIP en las posiciones fiscales que ya tienen percepciones: una factura toma una sola
    # posición fiscal, y el cliente que cae en una provincial también tiene que percibir SIRCIP. Las líneas
    # de las provincias que se van adhiriendo las saca el usuario a mano (ver README).
    for other in FiscalPos.search([("company_id", "=", company.id), ("id", "!=", fiscal_pos.id)]):
        perception_lines = other.l10n_ar_tax_ids.filtered(lambda x: x.tax_type == "perception")
        if perception_lines and not perception_lines.filtered(lambda x: x.default_tax_id.tax_group_id == tax_group):
            FiscalPosLine.create(dict(sircip_line_vals, fiscal_position_id=other.id))

    # 5. Diario de liquidación "SIRCIP Aplicado"
    if not env["account.journal"].search([("code", "=", "SIRC"), ("company_id", "=", company.id)], limit=1):
        settlement_account = env.ref("account.%s_ri_retencion_iibb_a_pagar" % company.id, raise_if_not_found=False)
        if settlement_account:
            partner_iibb = env.ref("l10n_ar.par_iibb_pagar", raise_if_not_found=False)
            env["account.journal"].with_company(company).create(
                {
                    "type": "general",
                    "name": "Liquidación SIRCIP Aplicado",
                    "code": "SIRC",
                    "tax_settlement": "allow_per_line",
                    "settlement_tax": "iibb_aplicado_sircip",
                    "settlement_partner_id": partner_iibb.id if partner_iibb else False,
                    "settlement_account_id": settlement_account.id,
                    "company_id": company.id,
                    "show_on_dashboard": False,
                    "settlement_account_tag_ids": [Command.set(tag.ids)],
                }
            )


def _setup_demo_sircip_padron_data(env):
    """Guarda en los partners demo los datos del padrón demo del mes, como pasa al facturarles por primera
    vez, para que se vean en la solapa Contabilidad del contacto."""
    fiscal_pos = env.ref("l10n_ar_sircip.fiscal_position_sircip_%s" % env.ref("base.company_ri").id)
    fp_line = fiscal_pos.l10n_ar_tax_ids[:1]
    today = fields.Date.context_today(fp_line)
    padron = fp_line._search_padron_file(fp_line._get_sircip_state(), today)
    if not padron:
        return
    for partner in env["res.partner"].search([("name", "=like", "SIRCIP Demo%")]):
        fp_line._sircip_get_padron_data(partner, today)
    _logger.info(
        "l10n_ar_sircip: datos del padrón demo cargados en los partners demo (%s).", today + relativedelta(day=1)
    )
