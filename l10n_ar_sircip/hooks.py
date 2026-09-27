##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64
import logging
import re

from dateutil.relativedelta import relativedelta
from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tools import file_open

from .models.account_tax import (
    SIRCIP_RECORD_NOT_REGISTERED,
    SIRCIP_RECORD_PERCEPTION,
    SIRCIP_RECORD_SURCHARGE,
)

_logger = logging.getLogger(__name__)

# Per-company templates: (xmlid key, name, amount, DDJJ record type, active).
# Perception and surcharge templates are copied per aliquot/province at invoice time.
# Names are the legal wording the Comisión Arbitral requires on the invoice.
SIRCIP_TAXES = [
    ("tax_sircip_percepcion", "Percepción SIRCIP", 0.0, SIRCIP_RECORD_PERCEPTION, False),
    ("tax_sircip_no_inscripto", "Percepción SIRCIP por no inscripto", 2.0, SIRCIP_RECORD_NOT_REGISTERED, True),
    ("tax_sircip_sobretasa", "Percepción SIRCIP por falta de alta", 1.0, SIRCIP_RECORD_SURCHARGE, False),
]

# AFIP tribute code of IIBB perceptions, same as the l10n_ar provincial groups
_AFIP_TRIBUTE_IIBB = "07"


def l10n_ar_sircip_post_init_hook(env):
    """With demo data, set the demo RI company as SIRCIP agent with its padron; otherwise do nothing."""
    company = env.ref("base.company_ri", raise_if_not_found=False)
    if not company or not env.ref("base.user_demo", raise_if_not_found=False):
        return
    company.l10n_ar_sircip_agent = True
    company._l10n_ar_sircip_setup()
    _setup_demo_sircip_padron_data(env)


def _xmlid(env, name, record):
    env["ir.model.data"].create(
        {"name": name, "module": "l10n_ar_sircip", "model": record._name, "res_id": record.id, "noupdate": True}
    )


def _get_or_create_account(env, company):
    """Return the settings account, or create one next to the chart's applied IIBB perception account."""
    if company.l10n_ar_sircip_account_id:
        return company.l10n_ar_sircip_account_id
    account = env.ref("l10n_ar_sircip.account_sircip_%s" % company.id, raise_if_not_found=False)
    if not account:
        sibling = env.ref("account.%s_ri_percepcion_iibb_tf_aplicada" % company.id, raise_if_not_found=False)
        if not sibling:
            raise UserError(
                env._(
                    "The chart of accounts of %(company)s has no account for applied IIBB perceptions. Set the "
                    "'SIRCIP Perception Account' in the Accounting settings.",
                    company=company.name,
                )
            )
        Account = env["account.account"].with_company(company)
        account = Account.create(
            {
                "name": "Percepción IIBB SIRCIP aplicada",
                "code": Account._search_new_account_code(sibling.with_company(company).code),
                "account_type": sibling.account_type,
                "company_ids": [Command.link(company.id)],
            }
        )
        _xmlid(env, "account_sircip_%s" % company.id, account)
    company.l10n_ar_sircip_account_id = account
    return account


def _create_sircip_data_for_company(env, company, sircip_state):
    Tax = env["account.tax"].with_company(company)
    FiscalPos = env["account.fiscal.position"].with_company(company)
    FiscalPosLine = env["account.fiscal.position.l10n_ar_tax"].with_company(company)

    tax_group = env.ref("l10n_ar_sircip.tax_group_sircip_%s" % company.id, raise_if_not_found=False)
    if not tax_group:
        tax_group = (
            env["account.tax.group"]
            .with_company(company)
            .create({"name": "SIRCIP", "company_id": company.id, "l10n_ar_tribute_afip_code": _AFIP_TRIBUTE_IIBB})
        )
        _xmlid(env, "tax_group_sircip_%s" % company.id, tax_group)

    # Templates share the account and tag the settlement journal relies on
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

    # Catch-all fiscal position, last among the perception ones
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
                # Without an AFIP responsibility the position is never auto-applied
                "l10n_ar_afip_responsibility_type_ids": [Command.set(ivari.ids)] if ivari else [],
                "l10n_ar_tax_ids": [Command.create(sircip_line_vals)],
            }
        )
        _xmlid(env, "fiscal_position_sircip_%s" % company.id, fiscal_pos)

    # An invoice takes a single fiscal position, so every one with perceptions also needs the SIRCIP line
    for other in FiscalPos.search([("company_id", "=", company.id), ("id", "!=", fiscal_pos.id)]):
        perception_lines = other.l10n_ar_tax_ids.filtered(lambda x: x.tax_type == "perception")
        if perception_lines and not perception_lines.filtered(lambda x: x.default_tax_id.tax_group_id == tax_group):
            FiscalPosLine.create(dict(sircip_line_vals, fiscal_position_id=other.id))

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
    """Load the demo padron for the current month and store the demo partners' padron data, as a first invoice
    would."""
    company = env.ref("base.company_ri")
    today = fields.Date.context_today(env["res.company.jurisdiction.padron"])
    month_start = today + relativedelta(day=1)
    period = month_start.strftime("%Y%m").encode()
    with file_open("l10n_ar_sircip/demo/padron_sircip_demo.txt", "rb") as demo_file:
        content = re.sub(rb"^\d{6},", period + b",", demo_file.read(), flags=re.M)
    padron = env["res.company.jurisdiction.padron"].create(
        {
            "company_id": company.id,
            "state_id": env.ref("l10n_ar_sircip.state_ar_sircip").id,
            "l10n_ar_padron_from_date": month_start,
            "l10n_ar_padron_to_date": month_start + relativedelta(months=1, days=-1),
            "filename": "padron_sircip_%s.txt" % period.decode(),
            "file_padron": base64.b64encode(content),
        }
    )
    _xmlid(env, "padron_sircip_demo", padron)
    fp_line = env.ref("l10n_ar_sircip.fiscal_position_sircip_%s" % company.id).l10n_ar_tax_ids[:1]
    for partner in env["res.partner"].search([("name", "=like", "SIRCIP Demo%")]):
        fp_line._sircip_get_padron_data(partner, today)
    _logger.info("l10n_ar_sircip: demo padron loaded for period %s.", period.decode())
