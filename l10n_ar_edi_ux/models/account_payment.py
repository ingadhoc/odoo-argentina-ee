from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # Diario de tipo varios que está vinculado al diario del pago del cheque (ver campo Check Debit Journal en el diario) para que nos permita hacer el débito del cheque.
    # Lo utilizamos como un diario "puente". Si no está establecido entonces usamos este campo para hacer invisible el botón para debitar cheques en la vista form del payment (es decir, del cheque).
    check_debit_journal_id = fields.Many2one(related='journal_id.check_debit_journal_id', readonly=True)
