##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


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
        third_checks = self.env['account.payment']
        # _get_checks_to_date_on_state('holding', self.to_date, force_domain=force_domain).sorted(key=lambda r:r.check_id.payment_date or r.check_id.issue_date)

        # cheques propios entregados
        own_checks = self.env['account.payment']
        # _get_checks_to_date_on_state('handed', self.to_date, force_domain=force_domain).sorted(key=lambda r:r.check_id.payment_date or r.check_id.issue_date)

        datadict = {
            'third_checks': third_checks,
            'own_checks': own_checks,
            'date': self.to_date.strftime('%d/%m/%Y'),
            'journal': self.journal_id.id
        }

        return self.env.ref('l10n_ar_account_reports.checks_to_date_report').report_action([], data=datadict)

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
