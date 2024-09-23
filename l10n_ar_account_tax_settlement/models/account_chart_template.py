##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api
import logging
_logger = logging.getLogger(__name__)
from odoo.addons.account.models.chart_template import template

class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @api.model
    def _get_country_code(self):
        """ Return the list of country codes for the countries where third party checks journals should be created
        when installing the COA"""
        return ["AR"]

    @template(model='account.journal')
    def _get_latam_withholding_account_journal(self, template_code=False, company=False):
        """ Creamos diarios de tipo 'varios' para liquidación de impuestos cuando se instala el plan de cuentas de la compañía. Los diarios a crear dependen de la condición fiscal de la compañía """
        company = company or self.env.company
        if company.country_id.code in self._get_country_code():
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

    @template('ar_ri', 'account.tax')
    def _get_ar_ri_withholding_account_tax(self):
        """ En caso de que se creen nuevas compañías argentinas responsable inscripto con su plan de cuentas correspondiente entonces a los impuestos creados de retenciones de ganancias e iva les agregamos el código de impuesto. """
        taxes_creados = super()._get_ar_ri_withholding_account_tax()
        company = self.env.company
        # verificamos que la compañía sea argentina y responsable inscripto
        if company.country_id.code in self._get_country_code() and company.l10n_ar_afip_responsibility_type_id.code == '1':
            if taxes_creados:
                taxes_creados.get('ri_tax_withholding_ganancias_applied')['codigo_impuesto'] = '01'
                taxes_creados.get('ri_tax_withholding_vat_applied')['codigo_impuesto'] = '02'
                taxes_creados.get('ri_tax_withholding_ganancias_applied')['withholding_type'] = 'tabla_ganancias'
                taxes_creados.get('ri_tax_withholding_ganancias_applied')['withholding_accumulated_payments'] = 'month'
                taxes_creados.get('ri_tax_withholding_ganancias_applied')['withholding_amount_type'] = 'untaxed_amount'
        return taxes_creados

    def _add_wh_taxes(self, company):
        """ Agregamos etiquetas en repartition lines de impuestos de percepciones de iva, ganancias e ingresos brutos.  """
        if company.country_id.code in self._get_country_code() and company.l10n_ar_afip_responsibility_type_id.code == '1':
            # Listado de impuesto-etiquetas a agregar, el primer elemento de cada tupla es el id del impuesto, los restantes son las etiquetas
            imp_etiq_list = [('ri_tax_percepcion_iva_aplicada', 'tag_ret_perc_sicore_aplicada'),
                             ('ri_tax_withholding_ganancias_applied', 'tag_ret_perc_sicore_aplicada'),
                             ('ri_tax_percepcion_ganancias_aplicada', 'tag_ret_perc_sicore_aplicada'),
                             ('ri_tax_percepcion_iibb_caba_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_901'),
                             ('ri_tax_percepcion_iibb_ba_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_902'),
                             ('ri_tax_percepcion_iibb_co_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_904'),
                             ('ri_tax_percepcion_iibb_sf_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_921'),
                             ('ri_tax_percepcion_iibb_ca_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_903'),
                             ('ri_tax_percepcion_iibb_rr_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_905'),
                             ('ri_tax_percepcion_iibb_er_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_908'),
                             ('ri_tax_percepcion_iibb_ju_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_910'),
                             ('ri_tax_percepcion_iibb_za_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_913'),
                             ('ri_tax_percepcion_iibb_lr_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_912'),
                             ('ri_tax_percepcion_iibb_sa_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_917'),
                             ('ri_tax_percepcion_iibb_nn_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_918'),
                             ('ri_tax_percepcion_iibb_sl_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_919'),
                             ('ri_tax_percepcion_iibb_se_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_922'),
                             ('ri_tax_percepcion_iibb_tn_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_924'),
                             ('ri_tax_percepcion_iibb_ha_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_906'),
                             ('ri_tax_percepcion_iibb_ct_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_907'),
                             ('ri_tax_percepcion_iibb_fo_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_909'),
                             ('ri_tax_percepcion_iibb_mi_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_914'),
                             ('ri_tax_percepcion_iibb_ne_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_915'),
                             ('ri_tax_percepcion_iibb_lp_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_911'),
                             ('ri_tax_percepcion_iibb_rn_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_916'),
                             ('ri_tax_percepcion_iibb_az_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_920'),
                             ('ri_tax_percepcion_iibb_tf_sufrida', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_923'),
                             ('ri_tax_withholding_iibb_caba_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_901'),
                             ('ri_tax_withholding_iibb_ba_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_902'),
                             ('ri_tax_withholding_iibb_ca_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_903'),
                             ('ri_tax_withholding_iibb_co_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_904'),
                             ('ri_tax_withholding_iibb_rr_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_905'),
                             ('ri_tax_withholding_iibb_er_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_908'),
                             ('ri_tax_withholding_iibb_ju_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_910'),
                             ('ri_tax_withholding_iibb_za_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_913'),
                             ('ri_tax_withholding_iibb_lr_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_912'),
                             ('ri_tax_withholding_iibb_sa_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_917'),
                             ('ri_tax_withholding_iibb_nn_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_918'),
                             ('ri_tax_withholding_iibb_sl_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_919'),
                             ('ri_tax_withholding_iibb_sf_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_921'),
                             ('ri_tax_withholding_iibb_se_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_922'),
                             ('ri_tax_withholding_iibb_tn_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_924'),
                             ('ri_tax_withholding_iibb_ha_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_906'),
                             ('ri_tax_withholding_iibb_ct_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_907'),
                             ('ri_tax_withholding_iibb_fo_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_909'),
                             ('ri_tax_withholding_iibb_mi_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_914'),
                             ('ri_tax_withholding_iibb_ne_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_915'),
                             ('ri_tax_withholding_iibb_lp_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_911'),
                             ('ri_tax_withholding_iibb_rn_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_916'),
                             ('ri_tax_withholding_iibb_az_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_920'),
                             ('ri_tax_withholding_iibb_tf_incurred', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_923'),
                             ('ri_tax_percepcion_iibb_ba_aplicada', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_902'),
                             ('ri_tax_percepcion_iibb_sf_aplicada', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_921'),
                             ('ri_tax_percepcion_iibb_co_aplicada', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_904'),
                             ('ri_tax_percepcion_iibb_caba_aplicada', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_901'),
                             ('ri_tax_withholding_iibb_ba_applied', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_902'),
                             ('ri_tax_withholding_iibb_sf_applied', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_921'),
                             ('ri_tax_withholding_iibb_co_applied', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_904'),
                             ('ri_tax_withholding_iibb_caba_applied', 'tax_tag_a_cuenta_iibb', 'tag_tax_jurisdiccion_901'),
                             ]
            for imp_etiq in imp_etiq_list:
                xml_id_percep = "account.%s_%s" % (company.id, imp_etiq[0])
                # Identificamos el impuesto al que se le va a agregar la/s etiqueta/s
                impuesto = self.env.ref(xml_id_percep)
                # Identificamos en el impuesto cuál es el dentro de sus invoice_repartition_line_ids y refund_repartition_line_ids aquellas líneas
                # que tienen repartition_type = 'tax' así le agregamos la etiqueta correspondiente
                for repartition in ['invoice_repartition_line_ids', 'refund_repartition_line_ids']:
                    repartition_line = next((el for el in impuesto[repartition] if el['repartition_type'] == 'tax'), None)
                    # Agregamos la/s etiqueta/s, tiene que ser en una lista donde agreguemos los ids de las etiquetas
                    tag_ids = []
                    for etiq in imp_etiq[1:]:
                        tag_ids.append(self.env.ref('l10n_ar_ux.%s' % (etiq)).id)
                    repartition_line.tag_ids = tag_ids
                # Agregamos a los impuestos que correspondan el "Cálculo de impuestos --> Alícuota en el partner"
                if imp_etiq[0] in ['ri_tax_percepcion_iibb_ba_aplicada', 'ri_tax_percepcion_iibb_sf_aplicada', 'ri_tax_percepcion_iibb_co_aplicada', 'ri_tax_percepcion_iibb_caba_aplicada']:
                    impuesto.amount_type = 'partner_tax'
                if imp_etiq[0] in ['ri_tax_withholding_iibb_ba_applied', 'ri_tax_withholding_iibb_sf_applied', 'ri_tax_withholding_iibb_co_applied', 'ri_tax_withholding_iibb_caba_applied']:
                    impuesto.withholding_type = 'partner_tax'
                    impuesto.withholding_amount_type = 'untaxed_amount'

    def _load(self, template_code, company, install_demo=False):
        """ Luego de que creen los impuestos del archivo account.tax-ar_ri.csv de l10n_ar al instalar el plan de cuentas en la nueva compañìa argentina agregamos en este método las etiquetas que correspondan en los repartition lines. """
        # Llamamos a super para que se creen los impuestos
        res = super()._load(template_code, company, install_demo)
        company = company or self.env.company
        if not company.parent_id:
            self._add_wh_taxes(company)
        return res
