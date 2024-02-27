import ast

from odoo import fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression

class AccountFinancialReport(models.Model):
    _inherit = "account.financial.html.report"

    def create_tax_settlement_entry(self, journal):
        """
        Funcion que crea asiento de liquidación a partir de información del
        reporte y devuelve browse del asiento generado
        * from_report_id
        * force_context
        * context: periods_number, cash_basis, date_filter_cmp, date_filter,
        date_to, date_from, hierarchy_3, company_ids, date_to_cmp,
        date_from_cmp, all_entries
        * search_disable_custom_filters
        * from_report_model
        * active_id
        """
        self.ensure_one()

        # obtenemos lineas de este reporte que tengan revert (sin importar
        # dominio o no porque en realidad puede estar seteado en linea padre
        # sin dominio)
        revert_lines = self.line_ids.search([
            ('id', 'child_of', self.line_ids.ids),
            ('settlement_type', '=', 'revert'),
        ])

        # obtenemos todas las lineas hijas de las que obtuvimos que tengan
        # dominio (esto es para evitar tener que
        # configurar revert en cada linea hija)
        revert_lines = self.line_ids.search([
            ('id', 'child_of', revert_lines.ids),
            ('domain', '!=', False),
            ('settlement_type', 'in', ['revert', False])
        ])

        move_lines = self.env['account.move.line']
        # TODO podriamos en vez de usar el report_move_lines_action para
        # obtener domain, usar directamente el "_compute_line" o el "_get_sum"
        # pero deberiamos luego cambiar la logica del grouped move lines
        # o en realidad estariamos repidiento casi dos veces lo mismo
        domains = []
        for line in revert_lines:
            domains.append(line.report_move_lines_action()['domain'])
        domain = expression.OR(domains)

        lines_vals = journal._get_tax_settlement_entry_lines_vals(domain)

        balance = sum([x['debit'] - x['credit'] for x in lines_vals])
        if not journal.company_id.currency_id.is_zero(balance):
            account_id = self._context.get('counterpart_account_id')
            if not account_id:
                raise ValidationError('El asiento de liquidación no está balanceado. Debe configurar una cuenta de contrapartida en el asistente para poder realizar el mismo.')

            lines_vals.append({
                # 'name': self.settlement_title,
                'name': 'Contrapartida',
                'debit': balance < 0.0 and -balance,
                'credit': balance >= 0.0 and balance,
                'account_id': account_id,
            })

        vals = journal._get_tax_settlement_entry_vals(lines_vals)
        move = self.env['account.move'].create(vals)

        if self._context.get('tax_settlement_link', True):
            move_lines.write({'tax_settlement_move_id': move.id})
        return move


class AccountFinancialReportLine(models.Model):
    _inherit = "account.financial.html.report.line"

    settlement_type = fields.Selection([
        ('new_line', 'New Journal Item'),
        ('new_line_negative', 'DEPRECIADO'),
        ('revert', 'DEPRECIADO'),
    ], help="If you choose:\n"
        "* New Journal Item: a new journal item with selected account will be "
        "created\n"
        "* New Journal Item (negative): a new journal item with selected "
        "account will be created (amount * -1)"
        "* Revert Journal Item: a line reverting this line will be created",
    )
    settement_account_tag_id = fields.Many2one(
        'account.account.tag',
        domain=[('applicability', '=', 'accounts')],
        context={'default_applicability': 'accounts'},
        string='Etiquetas de Cuenta',
        help='Si se eligió "Nuevo Apunte Contable", para la nueva línea, '
        'Se va a buscar una cuenta con esta etiqueta de cuenta',
    )

    # MAQ 04/01/2024: Reagrego este metodo eliminado en el
    # commit https://github.com/odoo/enterprise/pull/6620/files#diff-4507134a8f28a882a48d003e8d8d43b75036a10322780fb7134baa2abfeefeff
    # porque lo usabamos. Otra posibilidad es utilizar el metodo action_view_journal_entries
    # Pero requeriria una refatorizacion del nuestro codigo porque no es exactamente igual
    def report_move_lines_action(self):
        domain = ast.literal_eval(self.domain)
        if 'date_from' in self.env.context.get('context', {}):
            if self.env.context['context'].get('date_from'):
                domain = expression.AND([domain, [('date', '>=', self.env.context['context']['date_from'])]])
            if self.env.context['context'].get('date_to'):
                domain = expression.AND([domain, [('date', '<=', self.env.context['context']['date_to'])]])
            if self.env.context['context'].get('state', 'all') == 'posted':
                domain = expression.AND([domain, [('move_id.state', '=', 'posted')]])
            if self.env.context['context'].get('company_ids'):
                domain = expression.AND([domain, [('company_id', 'in', self.env.context['context']['company_ids'])]])
        return {'type': 'ir.actions.act_window',
                'name': 'Journal Items (%s)' % self.name,
                'res_model': 'account.move.line',
                'view_mode': 'tree,form',
                'domain': domain,
                }
