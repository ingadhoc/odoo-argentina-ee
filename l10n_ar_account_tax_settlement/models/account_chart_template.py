##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models
import logging
_logger = logging.getLogger(__name__)
from odoo.addons.account.models.chart_template import template

class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template(model='account.journal')
    def _get_latam_withholding_account_journal(self, template_code=False, company=False):
        """ Creamos diarios de tipo 'varios' para liquidación de impuestos cuando se instala el plan de cuentas de la compañía. Los diarios a crear dependen de la condición fiscal de la compañía """
        company = company or self.env.company
        if company.country_id.code in ["AR"]:
            journals_data = [
                ('Liquidación de IIBB', 'IIBB', 'allow_per_line', 'iibb_sufrido',
                    self.env.ref('l10n_ar.par_iibb_pagar'),
                    'base_iibb_a_pagar',
                    self.env.ref('l10n_ar_ux.tax_tag_a_cuenta_iibb'))
                ]
            if template_code == 'ar_ri':
                journals_data += [
                    ('Liquidación de IVA', 'IVA', 'yes', False,
                        self.env.ref('l10n_ar.partner_afip'),
                        'ri_iva_saldo_a_pagar',
                        self.env.ref('l10n_ar_ux.tax_tag_a_cuenta_iva'))]

            if template_code in ('ar_ri', 'ar_ex'):
                journals_data += [
                    ('Liquidación de Ganancias', 'GAN', 'yes', False,
                        # ref('l10n_ar_ux_reports.'
                        #     'account_financial_report_profits_position'),
                        self.env.ref('l10n_ar.partner_afip'),
                        'base_impuesto_ganancias_a_pagar',
                        self.env.ref('l10n_ar_ux.tax_tag_a_cuenta_ganancias')),
                    # only if account_withholding_automatic installed we
                    # set sicore_aplicado for txt
                    ('Liquidación SICORE Aplicado', 'SICORE', 'allow_per_line',
                        'sicore_aplicado' or False,
                        self.env.ref('l10n_ar.partner_afip'),
                        'ri_retencion_sicore_a_pagar',
                        self.env.ref('l10n_ar_ux.tag_ret_perc_sicore_aplicada')),
                    ('Liquidación IIBB Aplicado', 'IB_AP', 'allow_per_line',
                        False,  # 'iibb_aplicado', (Se debe elegir segun provincia)
                        self.env.ref('l10n_ar.par_iibb_pagar'),
                        # TODO flatan crear estas cuentas!
                        'ri_retencion_iibb_a_pagar',
                        self.env.ref('l10n_ar_ux.tag_ret_perc_iibb_aplicada')),
                ]
            res = {}
            for name, code, type, tax, partner, account, tag in journals_data:
                if not account:
                    _logger.info("Skip creation of journal %s because we didn't found default account")
                    continue
                res[code] = {
                    'type': 'general',
                    'name': name,
                    'code': code,
                    'tax_settlement': type,
                    'settlement_tax': tax,
                    'settlement_partner_id': partner and partner.id or False,
                    'settlement_account_id': account,
                    'company_id': company.id,
                    # al final hicimos otro dashboard
                    'show_on_dashboard': False,
                    'settlement_account_tag_ids': tag and [(4, tag.id, False)],
                }
            return res
