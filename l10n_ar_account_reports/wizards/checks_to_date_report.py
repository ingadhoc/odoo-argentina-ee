##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountCheckToDateReportWizard(models.TransientModel):
    _name = 'account.check.to_date.report.wizard'
    _description = 'account.check.to_date.report.wizard'

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        domain=[
            '|',
            ('inbound_payment_method_line_ids.code', 'in', ['new_third_party_checks', 'in_third_party_checks']),
            ('outbound_payment_method_line_ids.code', 'in', ['out_third_party_checks', 'check_printing'])])
    to_date = fields.Date(
        'Hasta Fecha',
        required=True,
        default=fields.Date.today,
    )

    def action_confirm(self):
        self.ensure_one()
        raise UserError('Todavia no fue implementado en esta versión.')

        # cheques de tercero en mano
        third_ops = self._get_checks_on_hand()

        # cheques propios entregados
        issue_ops = self._get_checks_handed()

        datadict = {
            'third_ops_ids': third_ops.ids,
            'issue_ops_ids': issue_ops.ids,
            'date': self.to_date.strftime('%d/%m/%Y'),
            'journal': self.journal_id.id
        }

        return self.env.ref('l10n_ar_account_reports.checks_to_date_report').report_action([], data=datadict)

    @api.model
    def _get_checks_handed(self):
        # TODO se deve devolver el listado de cheques propios no debitados a la fecha
        # ordenados por check_payment_date o date si no está definido
        return self.env['account.payment']

    @api.model
    def _get_checks_on_hand(self):
        # TODO se debe terminar de implementar y mejorarlo
        # deberiamos ver de obtener todos los cheques en mano (teniendo en cuenta que puede haber operaciones de
        # movimiento) entre carteras y que efectivamente representen que sigue en mano. Tal vez debamos lograr sumar de
        # alguna manera los payments que representan el new third check a las operaciones de cheques propiamente dichas
        # con eso debería ser bastante similar a la versión anterior

        # buscamos operaciones anteriores a la fecha que definan este estado
        date = self.to_date
        journal_domain = self.journal_id and [
            ('check_id.journal_id', '=', self.journal_id.id)] or []

        checks = self.env['account.payment'].search([
            ('date', '<=', date),
            # TODO faltaría probablemente sumar cheques que podríamos haber entregado y fueron devueltos
            ('payment_method_line_id.code', '=', 'new_third_party_checks')] + journal_domain,
            order='check_payment_date, date')

        for check in checks:
            # buscamos si hay alguna otra operacion posterior para el cheque
            newer_op = self.env['account.payment'].search([
                ('date', '<=', date),
                ('id', '>', check.id),
                ('l10n_latam_check_id', '=', check.id),
            ])
            # si hay una operacion posterior borramos a este cheque porque
            # hubo una operacion posterior
            # TODO en realidad deberíamos valuar si esta operación posterior
            # noes un movimiento de chequera
            if newer_op:
                checks -= check
        return checks
