# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import models, api, fields
# from openerp.tools.translate import _
from openerp.tools.misc import formatLang


class account_invoice_by_state(models.AbstractModel):
    _name = "account.invoice_by_state"
    _description = "Facturas por Provincia"

    def _format(self, value):
        if self.env.context.get('no_format'):
            return value
        currency_id = self.env.user.company_id.currency_id
        if currency_id.is_zero(value):
            # don't print -0.0 in reports
            value = abs(value)
        return formatLang(self.env, value, currency_obj=currency_id)

    def _get_lines_vals(self, journal_type, state_ids):
        domain = [
            ('account_id.internal_type', 'not in', ['payable', 'receivable']),
            ('journal_id.type', '=', journal_type),
        ]
        tables, where_clause, where_params = self.env[
            'account.move.line']._query_get(domain)

        # tables es algo como
        # account_move_line, account_move as account_move_line__move_id
        if journal_type == 'sale':
            sign = "-"
        else:
            sign = "+"
        query = """
SELECT
    max(rp.state_id),
    move_id,
    %ssum(CASE WHEN tax_line_id IS NULL THEN balance ELSE 0 END)
        as base_amount,
    %ssum(CASE WHEN tax_line_id IS NOT NULL THEN balance ELSE 0 END)
        as tax_amount,
    %ssum(balance) as total_amount
FROM %s, res_partner as rp
    -- JOIN res_partner rp on account_move_line.partner_id = rp.id
WHERE %s AND account_move_line.partner_id = rp.id
GROUP BY move_id
            """ % (sign, sign, sign, tables, where_clause)
        self.env.cr.execute(query, where_params)
        results = self.env.cr.fetchall()

        vals = {
            'base_amount': 0.0,
            'tax_amount': 0.0,
            'total_amount': 0.0,
            'states': dict([(k, {
                'base_amount': 0.0,
                'tax_amount': 0.0,
                'total_amount': 0.0,
                'moves': {},
            }) for k in state_ids]),
        }

        for result in results:
            state_id, move_id, base_amount, tax_amount, total_amount = result
            vals['base_amount'] += base_amount
            vals['tax_amount'] += tax_amount
            vals['total_amount'] += total_amount
            vals['states'][state_id]['base_amount'] += base_amount
            vals['states'][state_id]['tax_amount'] += tax_amount
            vals['states'][state_id]['total_amount'] += total_amount
            vals['states'][state_id]['moves'][move_id] = {
                'base_amount': base_amount,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
            }

        return vals

    @api.model
    def _lines(self, line_id=None):
        context = self.env.context['context_id']
        states = self.env.ref('base.ar').state_ids
        states_dict = dict(
            [(k.id, k.name) for k in states] + [(None, 'Sin Provincia')])
        lines = []
        journal_type = self.env.context['journal_type']
        vals = self._get_lines_vals(journal_type, states_dict.keys())
        lines.append({
            'id': 0,
            'name': 'Total',
            'type': 'total',
            'footnotes': context._get_footnotes('total', 0),
            'columns': [
                self._format(vals['base_amount']),
                self._format(vals['tax_amount']),
                self._format(vals['total_amount']),
            ],
            'level': 0,
            'colspan': 6,
        })
        for state_id, state_name in states_dict.items():
            # esto es necesario para que al expandir no muestre los nombres
            # de las provincias
            if line_id and state_id != line_id:
                continue
            if not vals['states'][state_id]['moves']:
                continue
            state_vals = vals['states'][state_id]

            # Como el campo para folded es provincia y no acepta el valor
            # false y no sabemos como hacer que sea folded o no sin que de
            #  error por ahora lo mostramos siempre despleado al
            # "sin provincia"
            if (state_id is None or state_id in context.unfolded_states.ids):
                unfolded = True
            else:
                unfolded = False

            lines.append({
                'id': state_id,
                'name': state_name,
                'type': 'line',
                'footnotes': context._get_footnotes('line', state_id),
                'columns': [
                    self._format(state_vals['base_amount']),
                    self._format(state_vals['tax_amount']),
                    self._format(state_vals['total_amount']),
                ],
                'level': 2,
                'colspan': 6,
                'unfoldable': state_id and True or False,
                # 'unfolded': state_id and (
                #     state_id in context.unfolded_states.ids) or False,
                'unfolded': unfolded
            })
            if not unfolded:
                continue
            for move_id, read in vals['states'][state_id]['moves'].items():
                move = self.env['account.move'].browse(move_id)
                # Si queremos implementar el poder abrir el move tenemos
                # que extender la vista report_financial_line y ademas pasar
                # el action aca
                lines.append({
                    'id': move_id,
                    # TODO ver si queremos sacr el nombre en el excel
                    # como hacer para que salga impreso pero no aca
                    # 'name': state_name,
                    'name': '',
                    'type': 'move_id',
                    'footnotes': context._get_footnotes('move_id', move_id),
                    # 'action': ['account.move', move_id, 'View Move', False],
                    'columns': [
                        move.date,
                        move.display_name,
                        move.partner_id.name,
                        move.partner_id.cuit,
                        move.ref,
                        self._format(read['base_amount']),
                        self._format(read['tax_amount']),
                        self._format(read['total_amount']),
                    ],
                    'level': 1,
                })
        return lines

    @api.model
    def get_report_type(self):
        return self.env.ref(
            'account_reports.account_report_type_date_range_no_comparison')

    @api.model
    def get_template(self):
        return 'account_reports.report_financial'


class account_invoice_by_state_purchase(models.AbstractModel):
    _name = "account.invoice_by_state.purchase"
    _description = "Compras por Provincia"
    _inherit = "account.invoice_by_state"

    @api.model
    def get_title(self):
        return 'Compras por Provincia'

    @api.model
    def get_name(self):
        return 'account_invoice_by_state_purchase'

    @api.model
    def get_lines(self, context_id, line_id=None):
        if type(context_id) == int:
            context_id = self.env[
                'account.report.context.invoice_by_state.purchase'].search(
                    [['id', '=', context_id]])
        return self.with_context(
            date_from=context_id.date_from,
            date_to=context_id.date_to,
            context_id=context_id,
            company_ids=context_id.company_ids.ids,
            journal_type='purchase',
        )._lines(line_id=line_id)


class AccountReportContextPurchase(models.TransientModel):
    _name = "account.report.context.invoice_by_state.purchase"
    _description = "A particular context for Compras x prov report"
    _inherit = "account.report.context.common"

    fold_field = 'unfolded_states'
    unfolded_states = fields.Many2many(
        'res.country.state', 'account_invoice_by_state_puchase',
        string='Unfolded lines')

    def get_report_obj(self):
        return self.env['account.invoice_by_state.purchase']

    def get_columns_names(self):
        columns = [
            "Fecha",
            "Documento", "Proveedor", "CUIT", "Observaciones",
            "Importe Bruto", "Impuestos", "Total",
        ]
        return columns

    @api.multi
    def get_columns_types(self):
        types = [
            'date',
            'text', 'text', 'text', 'text',
            'number', 'number', 'number',
        ]
        return types


class account_invoice_by_state_sale(models.AbstractModel):
    _name = "account.invoice_by_state.sale"
    _description = "Ventas por Provincia"
    _inherit = "account.invoice_by_state"

    @api.model
    def get_title(self):
        return 'Ventas por Provincia'

    @api.model
    def get_name(self):
        return 'account_invoice_by_state_sale'

    @api.model
    def get_lines(self, context_id, line_id=None):
        if type(context_id) == int:
            context_id = self.env[
                'account.report.context.invoice_by_state.sale'].search(
                    [['id', '=', context_id]])
        return self.with_context(
            date_from=context_id.date_from,
            date_to=context_id.date_to,
            context_id=context_id,
            company_ids=context_id.company_ids.ids,
            journal_type='sale',
        )._lines(line_id=line_id)


class AccountReportContextsale(models.TransientModel):
    _name = "account.report.context.invoice_by_state.sale"
    _description = "A particular context for Ventas x prov report"
    _inherit = "account.report.context.common"

    fold_field = 'unfolded_states'
    unfolded_states = fields.Many2many(
        'res.country.state', 'account_invoice_by_state_sale',
        string='Unfolded lines')

    def get_report_obj(self):
        return self.env['account.invoice_by_state.sale']

    def get_columns_names(self):
        columns = [
            "Fecha",
            "Documento", "Proveedor", "CUIT", "Observaciones",
            "Importe Bruto", "Impuestos", "Total",
        ]
        return columns

    @api.multi
    def get_columns_types(self):
        types = [
            'date',
            'text', 'text', 'text', 'text',
            'number', 'number', 'number',
        ]
        return types
