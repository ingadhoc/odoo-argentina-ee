##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging

from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

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

    # Demo mode: cargar alícuotas de los partners demo desde el padrón.
    # El hook corre DESPUÉS de que se carga la demo data, por lo que los
    # partners y el padrón ya existen en la base en este momento.
    if env.ref("base.user_demo", raise_if_not_found=False):
        _setup_demo_sircip_aliquots(env, sircip_state)


def _create_sircip_data_for_company(env, company, sircip_state):
    """Crea o actualiza los datos SIRCIP para una empresa dada.

    Nota: en Odoo 18, with_company() es un método de BaseModel (no de Environment).
    Usamos env["model"].with_company(company) para establecer el contexto de compañía.
    """
    # Helpers con contexto de compañía (with_company es método de BaseModel)
    TaxGroup = env["account.tax.group"].with_company(company)
    Tax = env["account.tax"].with_company(company)
    FiscalPos = env["account.fiscal.position"].with_company(company)
    FiscalPosLine = env["account.fiscal.position.l10n_ar_tax"].with_company(company)
    Journal = env["account.journal"].with_company(company)

    # 1. Grupo de impuestos
    tax_group = TaxGroup.search([("name", "=", "SIRCIP"), ("company_id", "=", company.id)], limit=1)
    if not tax_group:
        tax_group = TaxGroup.create({"name": "SIRCIP", "company_id": company.id})
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
        tax = Tax.search(
            [
                ("name", "=", name),
                ("company_id", "=", company.id),
                ("type_tax_use", "=", "sale"),
            ],
            limit=1,
        )
        if not tax:
            tax = Tax.create(
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
    fiscal_pos = FiscalPos.search(
        [
            ("name", "=", "Percepción - SIRCIP"),
            ("company_id", "=", company.id),
        ],
        limit=1,
    )
    if not fiscal_pos:
        fiscal_pos = FiscalPos.create(
            {
                "name": "Percepción - SIRCIP",
                "auto_apply": True,
                "sequence": 9999,
                "country_id": env.ref("base.ar").id,
                "company_id": company.id,
                "note": _(
                    "Exclusive fiscal position for SIRCIP perception agents "
                    "(Multilateral Agreement). Do not assign individual "
                    "provinces — detection is automatic."
                ),
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
        existing_line = FiscalPosLine.search(
            [
                ("fiscal_position_id", "=", fiscal_pos.id),
                ("tax_type", "=", "perception"),
                ("webservice", "=", "padron"),
            ],
            limit=1,
        )
        if not existing_line:
            FiscalPosLine.create(
                {
                    "fiscal_position_id": fiscal_pos.id,
                    "default_tax_id": default_tax.id,
                    "tax_type": "perception",
                    "webservice": "padron",
                }
            )

    # 5. Diario de liquidación "SIRCIP Aplicado"
    existing_journal = Journal.search([("code", "=", "SIRC"), ("company_id", "=", company.id)], limit=1)
    if not existing_journal:
        sircip_tag = env.ref("l10n_ar_ux.tag_ret_perc_iibb_aplicada", raise_if_not_found=False)
        partner_iibb = env.ref("l10n_ar.par_iibb_pagar", raise_if_not_found=False)
        account_xml_id = "account.%s_ri_retencion_iibb_a_pagar" % company.id
        settlement_account = env.ref(account_xml_id, raise_if_not_found=False)
        if settlement_account:
            Journal.create(
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
                    "settlement_account_tag_ids": [(4, sircip_tag.id)] if sircip_tag else [],
                }
            )


# XML IDs de los 5 partners demo SIRCIP
_DEMO_PARTNER_XMLIDS = [
    "l10n_ar_sircip.demo_partner_sircip_digit1",
    "l10n_ar_sircip.demo_partner_sircip_digit2",
    "l10n_ar_sircip.demo_partner_sircip_digit3",
    "l10n_ar_sircip.demo_partner_sircip_digit4",
    "l10n_ar_sircip.demo_partner_sircip_digit5",
]


def _setup_demo_sircip_aliquots(env, sircip_state):
    """Carga alícuotas SIRCIP para los partners demo desde el padrón demo.

    Se llama desde el post_init_hook solo cuando hay demo data.
    Simula lo que ocurre al crear la primera factura para cada partner:
    busca el CUIT en el padrón demo, lee la letra (alícuota) y el campo 7,
    y crea el registro l10n_ar.partner.tax con la trazabilidad completa.

    El padrón demo tiene un campo 7 diseñado para que idx=18 (Chaco, JC=906)
    tenga el dígito 1..5 según el caso de cada partner.
    """
    from_date = "2026-02-01"
    to_date = "2026-02-28"

    company_ri = env.ref("base.company_ri", raise_if_not_found=False)
    if not company_ri:
        return

    padron = env["res.company.jurisdiction.padron"].search(
        [
            ("state_id", "=", sircip_state.id),
            ("company_id", "=", company_ri.id),
        ],
        limit=1,
    )
    if not padron:
        _logger.info("l10n_ar_sircip: padrón demo no encontrado, se omite setup de alícuotas demo.")
        return

    sircip_group = env["account.tax.group"].search(
        [("name", "=", "SIRCIP"), ("company_id", "=", company_ri.id)],
        limit=1,
    )
    if not sircip_group:
        return

    created = 0
    for xmlid in _DEMO_PARTNER_XMLIDS:
        partner = env.ref(xmlid, raise_if_not_found=False)
        if not partner:
            continue

        # Idempotente: no crear duplicados
        if env["l10n_ar.partner.tax"].search(
            [
                ("partner_id", "=", partner.id),
                ("tax_id.tax_group_id", "=", sircip_group.id),
                ("from_date", "=", from_date),
                ("to_date", "=", to_date),
            ],
            limit=1,
        ):
            continue

        is_in, aliquot, campo7, crc = padron._get_sircip_aliquot(partner)
        if not is_in:
            _logger.warning("l10n_ar_sircip demo: CUIT %s no encontrado en padrón demo.", partner.vat)
            continue

        # Buscar o crear el impuesto SIRCIP con la alícuota de la letra
        tax = env["account.tax"].search(
            [
                ("amount", "=", aliquot),
                ("tax_group_id", "=", sircip_group.id),
                ("company_id", "=", company_ri.id),
                ("type_tax_use", "=", "sale"),
            ],
            limit=1,
        )
        if not tax:
            base_tax = env["account.tax"].search(
                [
                    ("tax_group_id", "=", sircip_group.id),
                    ("company_id", "=", company_ri.id),
                    ("type_tax_use", "=", "sale"),
                ],
                limit=1,
            )
            if not base_tax:
                continue
            name = "SIRCIP A 0.0" if aliquot == 0.0 else "SIRCIP %.2f%%" % aliquot
            tax = base_tax.copy(
                default={
                    "name": name,
                    "amount": aliquot,
                    "sequence": 10,
                    "active": True,
                    "l10n_ar_state_id": sircip_state.id,
                }
            )

        env["l10n_ar.partner.tax"].create(
            {
                "partner_id": partner.id,
                "tax_id": tax.id,
                "from_date": from_date,
                "to_date": to_date,
                "ref": "SIRCIP | crc:%s | campo7:%s" % (crc, campo7),
            }
        )
        created += 1

    if created:
        _logger.info("l10n_ar_sircip: %d alícuotas demo creadas para partners SIRCIP.", created)
