##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging

from odoo import Command, api, models
from odoo.addons.account.models.chart_template import template

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template(model="account.journal")
    def _get_latam_withholding_account_journal(self, template_code=False, company=False):
        """Creamos diarios de tipo 'varios' para liquidación de impuestos cuando se instala el plan de cuentas de la compañía. Los diarios a crear dependen de la condición fiscal de la compañía"""
        company = company or self.env.company
        if company.chart_template in ("ar_base", "ar_ri", "ar_ex"):
            journals_data = [
                (
                    "Liquidación de IIBB",
                    "IIBB",
                    "allow_per_line",
                    "iibb_sufrido",
                    self.env.ref("l10n_ar.par_iibb_pagar"),
                    "base_iibb_a_pagar",
                    self.env.ref("l10n_ar_ux.tax_tag_a_cuenta_iibb"),
                )
            ]
            if template_code == "ar_ri":
                journals_data += [
                    (
                        "Liquidación de IVA",
                        "IVA",
                        "yes",
                        False,
                        self.env.ref("l10n_ar.partner_afip"),
                        "ri_iva_saldo_a_pagar",
                        self.env.ref("l10n_ar_ux.tax_tag_a_cuenta_iva"),
                    )
                ]

            if template_code in ("ar_ri", "ar_ex"):
                journals_data += [
                    (
                        "Liquidación de Ganancias",
                        "GAN",
                        "yes",
                        False,
                        # ref('l10n_ar_ux_reports.'
                        #     'account_financial_report_profits_position'),
                        self.env.ref("l10n_ar.partner_afip"),
                        "base_impuesto_ganancias_a_pagar",
                        self.env.ref("l10n_ar_ux.tax_tag_a_cuenta_ganancias"),
                    ),
                    (
                        "Liquidación SICORE Aplicado",
                        "SICORE",
                        "allow_per_line",
                        "sicore_aplicado" or False,
                        self.env.ref("l10n_ar.partner_afip"),
                        "ri_retencion_sicore_a_pagar",
                        self.env.ref("l10n_ar_ux.tag_ret_perc_sicore_aplicada"),
                    ),
                    (
                        "Liquidación IIBB Aplicado",
                        "IB_AP",
                        "allow_per_line",
                        False,  # 'iibb_aplicado', (Se debe elegir segun provincia)
                        self.env.ref("l10n_ar.par_iibb_pagar"),
                        # TODO flatan crear estas cuentas!
                        "ri_retencion_iibb_a_pagar",
                        self.env.ref("l10n_ar_ux.tag_ret_perc_iibb_aplicada"),
                    ),
                ]
            res = {}
            for name, code, type, tax, partner, account, tag in journals_data:
                if not account:
                    _logger.info("Skip creation of journal %s because we didn't found default account")
                    continue
                account_id = "account.%s_%s" % (company.id, account)
                existing_journal = (
                    self.env["account.journal"]
                    .with_context(active_test=False)
                    .search([("company_id", "=", company.id), ("code", "=", code)], limit=1)
                )
                if existing_journal:
                    continue
                res[code] = {
                    "type": "general",
                    "name": name,
                    "code": code,
                    "tax_settlement": type,
                    "settlement_tax": tax,
                    "settlement_partner_id": partner and partner.id or False,
                    "settlement_account_id": account if self.env.ref(account_id, raise_if_not_found=False) else None,
                    "company_id": company.id,
                    # al final hicimos otro dashboard
                    "show_on_dashboard": False,
                    "settlement_account_tag_ids": tag and [(4, tag.id, False)],
                }
            return res

    def _load(self, template_code, company, install_demo, force_create=True):
        res = super()._load(template_code, company, install_demo, force_create)
        company = company or self.env.company
        if company.chart_template in ("ar_base", "ar_ri", "ar_ex"):
            self.sudo()._l10n_ar_create_sircip_suffered_tax(company)
        return res

    @api.model
    def _l10n_ar_create_sircip_suffered_tax(self, companies=None):
        """Create the purchase tax to register SIRCIP perceptions suffered from suppliers.

        Any Argentinian company may suffer them, agent or not. SIFERE Web loads them by itself once the agent files
        its DDJJ, so the tax is excluded from the SIFERE TXT, but it is settled in the IIBB journal like the
        provincial ones. Without ``companies`` it goes over every Argentinian company: the module data calls it so,
        on install and on every update, before the demo data uses the tax.
        """
        if companies is None:
            companies = self.env["res.company"].search([("chart_template", "in", ("ar_base", "ar_ri", "ar_ex"))])
        # Branches use the taxes of their parent company
        for company in companies.filtered(lambda x: not x.parent_id):
            xmlid = "tax_percepcion_iibb_sircip_sufrida_%s" % company.id
            if self.env.ref("l10n_ar_account_tax_settlement.%s" % xmlid, raise_if_not_found=False):
                continue
            tax_group = self.env.ref("account.%s_tax_group_percepcion_iibb" % company.id, raise_if_not_found=False)
            sibling = self.env.ref("account.%s_base_percepcion_iibb_tf_sufrida" % company.id, raise_if_not_found=False)
            if not tax_group or not sibling:
                _logger.info(
                    "Skip the SIRCIP suffered perception tax of %s: its chart lacks the IIBB ones", company.name
                )
                continue
            Account = self.env["account.account"].with_company(company)
            account = Account.create(
                {
                    "name": "Percepción IIBB SIRCIP sufrida",
                    "code": Account._search_new_account_code(sibling.with_company(company).code),
                    "account_type": sibling.account_type,
                    "company_ids": [Command.link(company.id)],
                }
            )
            tag = self.env.ref("l10n_ar_ux.tax_tag_a_cuenta_iibb", raise_if_not_found=False)
            repartition = [
                Command.create({"repartition_type": "base"}),
                Command.create(
                    {
                        "repartition_type": "tax",
                        "account_id": account.id,
                        "tag_ids": [Command.set(tag.ids if tag else [])],
                    }
                ),
            ]
            tax = (
                self.env["account.tax"]
                .with_company(company)
                .create(
                    {
                        "name": "Percepción SIRCIP sufrida",
                        "description": "Percepción IIBB SIRCIP",
                        "invoice_label": "Perc IIBB SIRCIP",
                        "sequence": 4,
                        "amount_type": "fixed",
                        "amount": 1.0,
                        "type_tax_use": "purchase",
                        "tax_group_id": tax_group.id,
                        "l10n_ar_sifere_excluded": True,
                        "company_id": company.id,
                        "invoice_repartition_line_ids": repartition,
                        "refund_repartition_line_ids": repartition,
                    }
                )
            )
            self.env["ir.model.data"].create(
                [
                    {
                        "name": name,
                        "module": "l10n_ar_account_tax_settlement",
                        "model": record._name,
                        "res_id": record.id,
                        "noupdate": True,
                    }
                    for name, record in [
                        (xmlid, tax),
                        ("account_percepcion_iibb_sircip_sufrida_%s" % company.id, account),
                    ]
                ]
            )
