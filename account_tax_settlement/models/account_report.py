import ast
from odoo import models, fields, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    allow_settlement = fields.Boolean(
        help='This optin will enable a new button on this report to settle all the lines that are of engine "domain".')
    settlement_title = fields.Char(translate=True)
    settlement_allow_unbalanced = fields.Boolean(
        help='If you enble this option, then an account will be required when creating the settlement entry and '
        'so that the balance of the report is sent to this account.')

    def _init_options_buttons(self, options, previous_options=None):
        super()._init_options_buttons(options, previous_options)
        if self.allow_settlement and self.settlement_title:
            options.setdefault('buttons', []).append({
                'name': '%s (BETA)' % self.settlement_title,
                'sequence': 150,
                'action': 'action_closure_journal_entry',
            })

    def action_closure_journal_entry(self, options):
        """ Abrimos wizard de liquidación para que se elija diario
        """
        self.ensure_one()

        companies = self.env['account.journal'].browse(
            [journal['id'] for journal in options.get('journals', []) if not journal['id'] in ('divider', 'group')]
            ).mapped('company_id')
        if len(companies) != 1:
            raise ValidationError(_('La liquidación se debe realizar filtrando por 1 y solo 1 compañía en el reporte'))
        if self.allow_settlement and self.settlement_title:
            action_name = '%s (BETA)' % self.settlement_title
            entry_ref = self.settlement_title

        new_context = {
            **self._context,
            'account_report_generation_options': options,
            'default_report_id': self.id,
            'entry_ref': entry_ref,
            'default_company_id': companies.id,
        }
        view_id = self.env.ref('account_tax_settlement.view_account_tax_settlement_wizard_form').id

        return {
            'type': 'ir.actions.act_window',
            'name': action_name,
            'view_mode': 'form',
            'res_model': 'account.tax.settlement.wizard',
            'target': 'new',
            'views': [[view_id, 'form']],
            'context': new_context,
        }

    def _report_create_settlement_entry(self, journal, options, account):
        """
        Funcion que crea asiento de cierre / refundicon.
        Basicamente busca todas las lineas del reporte que tienen engine domain, las evalua obteneindo domain de
        cada una, los manda a _get_tax_settlement_entry_lines_vals para obtener el reverso de todas estsas lineas
        y luego crea el asiento.
        Para el caso del asiento de refundicion.. TODO
        """
        self.ensure_one()

        options['unfold_all'] = True
        report_expressions = self.env['account.report.expression'].search(
            [('report_line_id', 'in', self.line_ids.ids), ('engine', '=', 'domain')])
        domains = []
        for report_expression in report_expressions:
            options_domain = self._get_options_domain(options, report_expression.date_scope)
            expression_domain = expression.AND([ast.literal_eval(report_expression.formula) + options_domain])
            domains.append(expression_domain)
        domain = expression.OR(domains)
        lines_vals = journal._get_tax_settlement_entry_lines_vals(domain)

        balance = sum([x['debit'] - x['credit'] for x in lines_vals])
        if not journal.company_id.currency_id.is_zero(balance):
            if not self.settlement_allow_unbalanced or not account:
                raise ValidationError(
                    'Parece que la liquidación quedaría desbalanceada. Si desea generar igualmente la liquidacion puede:\n'
                    '1. Ir a "Contabilidad / Configuración / Administración / Informes contables"\n'
                    '2. Buscar el informe correspondiente\n'
                    '3. En opciones, marcar "Settlement Allow Unbalanced"\n'
                    '4. Puede volver a crear el asiento de liqidación seleccionando la cuenta de contrapartida que le sea solicitada')
            lines_vals.append({
                'name': self.settlement_title,
                'debit': balance < 0.0 and -balance,
                'credit': balance >= 0.0 and balance,
                'account_id': account.id,
            })

        vals = journal._get_tax_settlement_entry_vals(lines_vals)
        move = self.env['account.move'].with_context(allow_no_partner=True).create(vals)

        return move
