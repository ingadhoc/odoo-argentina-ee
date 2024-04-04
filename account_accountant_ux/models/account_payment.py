from odoo import models, api
from odoo.exceptions import  ValidationError

class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    @api.constrains('payment_method_line_id')
    def _check_payment_method_line_id(self):
        ''' Ensure the 'payment_method_line_id' field is not null.
        Can't be done using the regular 'required=True' because the field is a computed editable stored one.
        '''
        for pay in self:
            if not pay.payment_method_line_id:
                raise ValidationError(_("Please define a payment method line on your payment."))
