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
        # Obtenemos fecha, importe, pasamos cuenta outstanding y el diario es de tipo varios que está vinculado al diario del pago del cheque (ver campo Check Debit Journal en el diario) para que nos permita hacer la conciliación. Lo utilizamos como un diario "puente".
        new_mv_line_dicts = [{'name': f'Débito cheque nro {payment.check_number}',
                            'balance': abs(sum(liquidity_lines.mapped('balance'))),
                            'account_id': outstanding_account.id,
                            'journal_id': payment.journal_id.check_debit_journal_id.id,
                            'date': self.date,
                            }]
        self.env['account.reconciliation.widget']._process_move_lines(move_line_ids, new_mv_line_dicts)
        payment.message_post(body=f'El cheque nro "{payment.check_number}" ha sido debitado.')

    def _get_outstanding_account(self, payment):
        """ Obtenemos la cuenta outstanding para hacer el débito de cheques y hacemos las validaciones correspondientes. """
        journal = payment.journal_id
        journal_manual_payment_method = journal.outbound_payment_method_line_ids.filtered(lambda x: x.code=='manual')
        outstanding_account = (journal_manual_payment_method.payment_account_id or journal.company_id.account_journal_payment_credit_account_id)
        if not outstanding_account:
            raise UserError("No es posible crear un nuevo débito de cheque sin una cuenta outstanding de pagos establecida ya sea en la compañía o en el método de pagos 'manual' en el diario %s." % (payment.journal_id.display_name))
        return outstanding_account
