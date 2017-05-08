# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import models, api
# from openerp.tools.translate import _
from openerp.tools.misc import formatLang


class account_iva_f2002_report(models.AbstractModel):
    _name = "account.iva_f2002.report"
    _description = "IVA F2002 Tax Report"

    def _format(self, value):
        if self.env.context.get('no_format'):
            return value
        currency_id = self.env.user.company_id.currency_id
        if currency_id.is_zero(value):
            # don't print -0.0 in reports
            value = abs(value)
        return formatLang(self.env, value, currency_obj=currency_id)

    @api.model
    def get_lines(self, context_id, line_id=None):
        return self.with_context(
            date_from=context_id.date_from,
            date_to=context_id.date_to,
            context_id=context_id,
            company_ids=context_id.company_ids.ids,
        )._lines()

    def _get_lines_vals(self, date_from, date_to, categs_list, tax_group_list):
        """
        Hicimos esta funcion que genera un diccionario con:
        * tax groups: donde para cada tax group hay un diccionario con
            * tax:
            * base:
            * categs: donde para categ hay un diccionario con
                * tax:
                * base:
        Tuvimos que hacerlo asi porque calcular la base la podemos hacer
        sensillamente por categoria pero no para el iva porque el iva esta
        agrupado y no discriminado por producto.
        Entonces de esta manera sumamos todos los ivas netos y los distribuimos
        """
        vals = {}
        for base_column, tax_group in tax_group_list:
            tax_group_base = self.env[
                'account.move.line']._get_tax_move_lines_balance(
                    date_from, date_to, 'base',
                    tax_groups=tax_group)
            tax_group_tax = self.env[
                'account.move.line']._get_tax_move_lines_balance(
                    date_from, date_to, 'tax',
                    tax_groups=tax_group)
            vals[tax_group] = {
                'base': tax_group_base,
                'tax': tax_group_tax,
                'categs': {},
            }
            for categ_name, categ in categs_list:
                # se pide base column para los iva, para ret, perc y demas
                # que no tenemos el dato del base, tampoco los tenemos
                # clasificados por producto, por lo cual tomamos el total
                # y lo ponemos en sin categoria porque no hay base para
                # prorratear
                if base_column:
                    tax_group_categ_base = self.env[
                        'account.move.line']._get_tax_move_lines_balance(
                            date_from, date_to, 'base',
                            tax_groups=tax_group, f2002_category=categ)
                    tax_group_categ_tax = tax_group_base and (
                        tax_group_tax *
                        tax_group_categ_base / tax_group_base) or 0.0
                    vals[tax_group]['categs'][categ] = {
                        'base': tax_group_categ_base,
                        'tax': tax_group_categ_tax,
                    }
                elif categ is False:
                    vals[tax_group]['categs'][categ] = {
                        'base': tax_group_base,
                        'tax': tax_group_tax,
                    }
                else:
                    vals[tax_group]['categs'][categ] = {
                        'base': 0.0,
                        'tax': 0.0,
                    }
        return vals

    @api.model
    def _lines(self):
        context = self.env.context
        date_from = context.get('date_from')
        date_to = context.get('date_to')
        lines = []
        categs = self.env['afip.vat.f2002_category'].search([])

        ref = self.env.ref
        # If True, then we add a columns for base, if false, only tax amount
        tax_group_list = [
            (True, ref('l10n_ar_account.tax_group_iva_21')),
            (True, ref('l10n_ar_account.tax_group_iva_10')),
            (False, ref('l10n_ar_account.tax_group_percepcion_iva')),
        ]
        # tax_groups = [x[1] for x in tax_group_list]

        line_id = 0
        categs_list = [('Sin Categoría', False)] + categs.mapped(
            lambda x: (x.name, x))

        # for iva in ['IVA débito', 'IVA crédito']:
        for iva in ['sale', 'purchase']:
            # TODO ver como scamos esta suma
            line_vals = self._get_lines_vals(
                date_from, date_to, categs_list, tax_group_list)
            print 'line_vals', line_vals
            columns = []
            for base_column, tax_group in tax_group_list:
                if base_column:
                    columns.append(line_vals[tax_group]['base'])
                columns.append(line_vals[tax_group]['tax'])
            lines.append({
                'id': line_id,
                'name': iva,
                'type': 'line',
                'footnotes': context['context_id']._get_footnotes(
                    'line', line_id),
                'unfoldable': False,
                'columns': columns,
                'level': 1,
            })
            for categ_name, categ in categs_list:
                columns = []
                for base_column, tax_group in tax_group_list:
                    if base_column:
                        columns.append(
                            line_vals[tax_group]['categs'][categ]['base'])
                    columns.append(
                        line_vals[tax_group]['categs'][categ]['tax'])
                # for tax_group in tax_groups:
                #     columns += (
                #         line_vals[tax_group]['categs'][categ]['base'],
                #         line_vals[tax_group]['categs'][categ]['tax'])
                lines.append({
                    'id': line_id,
                    'name': categ_name,
                    'type': 'tax_id',
                    'footnotes': context['context_id']._get_footnotes(
                        'line', line_id),
                    'unfoldable': False,
                    'columns': columns,
                    # 'columns': [net_21, tax_21],
                    'level': 1,
                })
                line_id += 1
        return lines

    @api.model
    def get_title(self):
        return 'Reporte IVA web F2002'

    @api.model
    def get_name(self):
        return 'iva_f2002_report'

    @api.model
    def get_report_type(self):
        # return self.env.ref(
        #     'account_reports.account_report_type_no_date_range')
        return self.env.ref(
            'account_reports.account_report_type_date_range_no_comparison')
        # return self.env.ref('account_reports.account_report_type_date_range')

    @api.model
    def get_template(self):
        return 'account_reports.report_financial'


class AccountReportContextTax(models.TransientModel):
    _name = "account.report.context.iva_f2002"
    _description = "A particular context for IVA f2002 report"
    _inherit = "account.report.context.common"

    def get_report_obj(self):
        return self.env['account.iva_f2002.report']

    def get_columns_names(self):
        columns = [
            "Neto Gravado 21%", "IVA 21%",
            "Neto Gravado 10,5%", "IVA 10,5%",
            "Perc",
        ]
        return columns

    @api.multi
    def get_columns_types(self):
        types = [
            'number', 'number',
            'number', 'number',
            'number',
        ]
        return types
