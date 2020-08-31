from odoo import fields, models, api, _
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

        # agregamos otrs lineas ẗipo "new line"
        new_lines = self.line_ids.search([
            ('id', 'child_of', self.line_ids.ids),
            ('settlement_type', 'in', ['new_line', 'new_line_negative'])])

        # pasamos por contexto lo que viene adentro del contetxo como contexto
        # porque asi lo interpreta _get_balance (en vez aparentemente
        # report_move_lines_action busca dentro del contexto)
        new_lines = new_lines.with_context(
            new_lines._context.get('context'))
        for new_line in new_lines:
            account = self.env['account.account'].search([
                ('company_id', '=', journal.company_id.id),
                ('tag_ids', '=', new_line.settement_account_tag_id.id)],
                limit=1)
            if not account:
                raise ValidationError(_(
                    'No account found with tag "%s" (id: %s) for company "%s".'
                    ' Check report and accounts configuration.') % (
                    new_line.settement_account_tag_id.name,
                    new_line.settement_account_tag_id.id,
                    journal.company_id.name))
            balance = sum(
                [x['balance'] for x in new_line._get_balance(
                    {}, {}, self, field_names=['balance'])])
            if journal.company_id.currency_id.is_zero(balance):
                continue
            balance = new_line.settlement_type == 'new_line' \
                and balance or balance * -1.0
            lines_vals.append({
                'name': self.name,
                'debit': balance < 0.0 and -balance,
                'credit': balance >= 0.0 and balance,
                'account_id': account.id,
            })

        vals = journal._get_tax_settlement_entry_vals(lines_vals)
        move = self.env['account.move'].with_context(
            allow_no_partner=True).create(vals)

        if self._context.get('tax_settlement_link', True):
            move_lines.write({'tax_settlement_move_id': move.id})
        return move


class AccountFinancialReportLine(models.Model):
    _inherit = "account.financial.html.report.line"

    settlement_type = fields.Selection([
        ('new_line', 'New Journal Item'),
        ('new_line_negative', 'New Journal Item (negative)'),
        ('revert', 'Revert Journal Item'),
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
