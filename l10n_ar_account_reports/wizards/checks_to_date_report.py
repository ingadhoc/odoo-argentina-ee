##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api


class AccountCheckToDateReportWizard(models.TransientModel):
    _name = 'account.check.to_date.report.wizard'
    _description = 'account.check.to_date.report.wizard'

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        domain=[
            '|',
            ('outbound_payment_method_line_ids.code', '=', 'check_printing'),
            ('inbound_payment_method_line_ids.code', '=', 'in_third_party_checks'),
            ],
    )
    to_date = fields.Date(
        'Hasta Fecha',
        required=True,
        default=fields.Date.today,
    )

    def action_confirm(self):
        self.ensure_one()
        force_domain = self.journal_id and [('journal_id', '=', self.journal_id.id)] or []

        # cheques de tercero en mano
        # third_checks = self.env['account.payment']
        # # _get_checks_to_date_on_state('holding', self.to_date, force_domain=force_domain).sorted(key=lambda r:r.check_id.payment_date or r.check_id.issue_date)

        # # cheques propios entregados
        # own_checks = self.env['account.payment']
        # _get_checks_to_date_on_state('handed', self.to_date, force_domain=force_domain).sorted(key=lambda r:r.check_id.payment_date or r.check_id.issue_date)

        # datadict = {
        #     'third_checks': third_checks,
        #     'own_checks': own_checks,
        #     'date': self.to_date.strftime('%d/%m/%Y'),
        #     'journal': self.journal_id.id
        # }

        # return self.env.ref('l10n_ar_account_reports.checks_to_date_report').report_action([], data=datadict)
        return self.env.ref('l10n_ar_account_reports.checks_to_date_report').report_action(self)

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
        journal_domain = self.journal_id and [('journal_id', '=', self.journal_id.id)] or []

        payments = self.env['account.payment'].search(journal_domain + [
            ('date', '<=', date),
            ('payment_method_line_id.code', 'in', ['new_third_party_checks', 'in_third_party_checks']),
            ])
        checks = self.env['account.payment']
        for payment in payments:
            # buscamos si hay alguna otra operacion posterior para el cheque
            newer_op = payment.search([
                ('date', '<=', date),
                ('id', '>', payment.id),
                ('l10n_latam_check_id', '=',
                    payment.id if payment.payment_method_line_id.code == 'new_third_party_checks' else
                    payment.l10n_latam_check_id),
            ])
            # si hay una operacion posterior borramos a este cheque porque
            # hubo una operacion posterior
            # TODO en realidad deberíamos valuar si esta operación posterior
            # noes un movimiento de chequera
            if newer_op:
                continue
            elif payment.payment_method_line_id.code == 'new_third_party_checks':
                checks |= payment
            else:
                checks |= payment.l10n_latam_check_id
        return checks

    # @api.model
    # def _get_checks_to_date_on_state(self, state, date, force_domain=None):
    #     """
    #     Devuelve el listado de cheques que a la fecha definida se encontraban
    #     en el estadao definido.
    #     Esta función no la usamos en este módulo pero si en otros que lo
    #     extienden
    #     La funcion devuelve un listado de las operaciones a traves de las
    #     cuales se puede acceder al cheque, devolvemos las operaciones porque
    #     dan información util de fecha, partner y demas
    #     """
    #     # buscamos operaciones anteriores a la fecha que definan este estado
    #     if not force_domain:
    #         force_domain = []

    #     operations = self.operation_ids.search([
    #         ('date', '<=', date),
    #         ('operation', '=', state)] + force_domain)

    #     for operation in operations:
    #         # buscamos si hay alguna otra operacion posterior para el cheque
    #         newer_op = operation.search([
    #             ('date', '<=', date),
    #             ('id', '>', operation.id),
    #             ('check_id', '=', operation.check_id.id),
    #         ])
    #         # si hay una operacion posterior borramos la op del cheque porque
    #         # hubo otra operación antes de la fecha
    #         if newer_op:
    #             operations -= operation
    #     return operations
