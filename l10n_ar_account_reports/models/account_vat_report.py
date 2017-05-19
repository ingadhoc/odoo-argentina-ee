# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import models, api, fields
# from openerp.tools.translate import _
from openerp.tools.misc import formatLang


class AccountVatReport(models.AbstractModel):
    _name = "account.vat.report"
    _description = "Libro IVA"

    def _format(self, value):
        if self.env.context.get('no_format'):
            return value
        currency_id = self.env.user.company_id.currency_id
        if currency_id.is_zero(value):
            # don't print -0.0 in reports
            value = abs(value)
        return formatLang(self.env, value, currency_obj=currency_id)

    def _get_lines_vals(self, journal_type):
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
        }

        for result in results:
            state_id, move_id, base_amount, tax_amount, total_amount = result
            vals[move_id] = {
                'base_amount': base_amount,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
            }
        return vals

    @api.model
    def _lines(self, line_id=None):
        context = self.env.context['context_id']
        lines = []
        journal_type = self.env.context['journal_type']
        # TODO reemplazar journal type por journals
        vals = self._get_lines_vals(journal_type)
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


class account_vat_report_purchase(models.AbstractModel):
    _name = "account.vat.report.purchase"
    _description = "Libro IVA Compras"
    _inherit = "account.vat.report"

    @api.model
    def get_title(self):
        return 'Libro IVA Compras'

    @api.model
    def get_name(self):
        return 'account_vat_report_purchase'

    @api.model
    def get_lines(self, context_id, line_id=None):
        if type(context_id) == int:
            context_id = self.env[
                'account.report.context.vat.purchase'].search(
                    [['id', '=', context_id]])
        return self.with_context(
            date_from=context_id.date_from,
            date_to=context_id.date_to,
            context_id=context_id,
            company_ids=context_id.company_ids.ids,
            journal_type='purchase',
            # es para que el query de los moves no traiga todo lo anterior
            strict_range=True,
        )._lines(line_id=line_id)


class AccountReportContextVatPurchase(models.TransientModel):
    _name = "account.report.context.vat.purchase"
    _description = "A particular context for Libro IVA Compras"
    _inherit = "account.report.context.common"

    journal_ids = fields.Many2many(
        'account.journal', relation='account_report_ivap_journals')
    available_journal_ids = fields.Many2many(
        'account.journal', relation='account_report_ivap_available_journal',
        default=lambda s: [(6, 0, s.env['account.journal'].search(
            [('type', '=', 'purchase')]).ids)])

    @api.multi
    def get_html_and_data(self, given_context=None):
        result = super(
            AccountReportContextVatPurchase, self).get_html_and_data()
        result['report_context'].update(self.read(['journal_ids'])[0])
        result['available_journals'] = (
            self.get_available_journal_ids_names_and_codes())
        return result

    @api.multi
    def get_available_journal_ids_names_and_codes(self):
        return [[c.id, c.name, c.code] for c in self.available_journal_ids]

    def get_report_obj(self):
        return self.env['account.vat.report.purchase']

    def get_columns_names(self):
        columns = [
            "Fecha", "Comprobante", "Proveedor", "CUIT", "Cond. IVA",
            # "Tipo"
            # TODO, agregar tipo como en xubio? factura, NC, Nd?
            # VAT columns
        ]
        return columns

    @api.multi
    def get_columns_types(self):
        types = [
            'date', 'text', 'text', 'text', 'text',
            # 'number', 'number', 'number',
        ]
        return types
