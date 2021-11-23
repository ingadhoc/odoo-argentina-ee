##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api
import logging
_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    def _create_bank_journals(self, company, acc_template_ref):
        res = super(
            AccountChartTemplate, self)._create_bank_journals(
            company, acc_template_ref)
        if company.country_id != self.env.ref('base.ar'):
            return res

        ref = self.env.ref

        def get_account(ext_id):
            """
            Helper para obtener referencia a alguna cuenta
            """
            return acc_template_ref.get(ref('l10n_ar.%s' % ext_id))

        # add more journals commonly used in argentina localization
        journals_data = [
            ('Liquidación de IIBB', 'IIBB', 'allow_per_line', 'iibb_sufrido',
                ref('l10n_ar.par_iibb_pagar'),
                get_account('base_iibb_a_pagar'),
                ref('l10n_ar_ux.tax_tag_a_cuenta_iibb'))
        ]

        chart = company.chart_template_id
        ri_chart = ref('l10n_ar.l10nar_ri_chart_template', False)
        ex_chart = ref('l10n_ar.l10nar_ex_chart_template', False)

        # iva solo para RI
        if chart == ri_chart:
            journals_data += [
                ('Liquidación de IVA', 'IVA', 'yes', False,
                    # ref('l10n_ar_ux_reports.'
                    #     'account_financial_report_vat_position'),
                    ref('l10n_ar.partner_afip'),
                    get_account('ri_iva_saldo_a_pagar'),
                    ref('l10n_ar_ux.tax_tag_a_cuenta_iva'))]

        account_withholding_automatic = self.env['ir.module.module'].search([
            ('name', '=', 'account_withholding_automatic'),
            ('state', '=', 'installed')])
        # por ahora, por mas que no tenga retenciones automaticas,
        # creamos los daiarios de liquidacion ya que es mas facil desactivarlos
        # que crearlos luego, y si es un ri lo mas probable es que deba
        # tenerlos

        # estas para mono no van, para exento y ri si
        if chart in (ri_chart, ex_chart):
            journals_data += [
                ('Liquidación de Ganancias', 'GAN', 'yes', False,
                    # ref('l10n_ar_ux_reports.'
                    #     'account_financial_report_profits_position'),
                    ref('l10n_ar.partner_afip'),
                    get_account('base_impuesto_ganancias_a_pagar'),
                    ref('l10n_ar_ux.tax_tag_a_cuenta_ganancias')),
                # only if account_withholding_automatic installed we
                # set sicore_aplicado for txt
                ('Liquidación SICORE Aplicado', 'SICORE', 'allow_per_line',
                    account_withholding_automatic and 'sicore_aplicado' or False,
                    ref('l10n_ar.partner_afip'),
                    get_account('ri_retencion_sicore_a_pagar'),
                    ref('l10n_ar_ux.tag_ret_perc_sicore_aplicada')),
                ('Liquidación IIBB Aplicado', 'IB_AP', 'allow_per_line',
                    False,  # 'iibb_aplicado', (Se debe elegir segun provincia)
                    ref('l10n_ar.par_iibb_pagar'),
                    # TODO flatan crear estas cuentas!
                    get_account('ri_retencion_iibb_a_pagar'),
                    ref('l10n_ar_ux.tag_ret_perc_iibb_aplicada')),
            ]

        # for name, code, tax, report, partner, credit_id, debit_id, tag \
        for name, code, type, tax, partner, account, tag in journals_data:
            if not account:
                _logger.info("Skip creation of journal %s because we didn't found default account")
                continue
            # journal_data.append({
            self.env['account.journal'].create({
                'type': 'general',
                'name': name,
                'code': code,
                'tax_settlement': type,
                'settlement_tax': tax,
                # 'settlement_financial_report_id': report and report.id,
                'settlement_partner_id': partner and partner.id or False,
                'default_account_id': account.id,
                'company_id': company.id,
                # al final hicimos otro dashboard
                'show_on_dashboard': False,
                'settlement_account_tag_ids': tag and [(4, tag.id, False)],
            })

        return res
