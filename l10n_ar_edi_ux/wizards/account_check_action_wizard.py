##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models
from odoo.exceptions import ValidationError, UserError


class AccountCheckActionWizard(models.TransientModel):
    _name = 'account.check.action.wizard'
    _description = 'Account Check Action Wizard'

    date = fields.Date(
        default=fields.Date.context_today,
        required=True,
    )

    def action_confirm(self):
        """ Este método sirve para hacer el débito de cheques con cuenta outstanding desde los payments con método de pago de cheques. """
        payment = self.env['account.payment'].browse(self._context.get('active_id', False))
        if self.date < payment.date:
            raise ValidationError(f'La fecha del débito del cheque {self.date} no puede ser inferior a la fecha de emisión del mismo {payment.date}.')
        # Línea del cheque a conciliar.
        liquidity_lines, counterpart_lines, writeoff_lines = payment._seek_for_lines()
        move_line_ids = liquidity_lines.ids
        # Obtenemos la cuenta outstanding del método de pago pentientes "manual" del diario del pago o bien la "Cuenta de pagos pentientes" de la compañía.
        outstanding_account = self._get_outstanding_account(payment)
        # Obtenemos fecha, importe, pasamos cuenta outstanding y el diario asignado es el mismo que se está editando.
        new_mv_line_dicts = {'label': f'Débito cheque nro {payment.check_number}',
                            'amount': abs(sum(liquidity_lines.mapped('balance'))),
                            'account_id': outstanding_account.id,
                            'journal_id': payment.journal_id.id,
                            'move_line_ids': move_line_ids,
                            'date': self.date
                            }
        # Aquí hacemos el asiento del débito.
        wizard = self.env['account.reconcile.wizard'].with_context(active_model='account.move.line', active_ids=move_line_ids).new({})
        for index, value in new_mv_line_dicts.items():
            wizard[index] = value
        wizard.reconcile()
        payment.message_post(body=f'El cheque nro "{payment.check_number}" ha sido debitado.')

    def _get_outstanding_account(self, payment):
        """ Obtenemos la cuenta para hacer el débito de cheques y hacemos las validaciones correspondientes. Siempre necesitamos que se encuentre establecido un método de pago manual en el diario para poder hacer el débito, no vamos a buscar la cuenta outstanding en configuración en caso de que no esté establecido el método de pago manual. Primero buscamos método de pago con code manual y nombre 'Manual' y si no lo encuentra buscamos el primer método de pago manual que se creó. """
        journal = payment.journal_id
        journal_manual_payment_method = journal.outbound_payment_method_line_ids.filtered(lambda x: x.code == 'manual')
        if not journal_manual_payment_method:
            raise UserError("No es posible crear un nuevo débito de cheque sin un método de pagos 'manual' en el diario %s." % (payment.journal_id.display_name))
        # si hay mas de un método de pago con code code manual tratamos de buscar uno con name Manual, si no lo hay usamos el primero
        if len(journal_manual_payment_method) > 1:
            if journal_manual_payment_method.filtered(lambda x: x.name == 'Manual'):
                journal_manual_payment_method = journal_manual_payment_method.filtered(lambda x: x.name == 'Manual')
            journal_manual_payment_method = journal_manual_payment_method.sorted()[0]
        return journal_manual_payment_method.payment_account_id
