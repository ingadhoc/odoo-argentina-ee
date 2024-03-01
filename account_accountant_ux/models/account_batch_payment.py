from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    @api.depends('payment_ids')
    def verify_unlinked_payments_from_batch(self):
        """don´t allow to unlink payments linked to the batch payment if the batch is not on draft state"""
        if (self._origin.filtered(lambda x: x.state != 'draft') and len(self._origin.payment_ids) != len(self.payment_ids)):
            raise UserError(_("You are not allowed to delete payments from a batch payment if the batch is not on draft state."))

    def unlink(self):
        """This method don't allow to delete an account batch payment if it's not on draft state"""
        if self.filtered(lambda x: x.state != 'draft'):
            raise UserError(_("You are not allowed to delete a batch payment if is not on draft state."))
        return super().unlink()

    def action_draft(self):
        """Only sent batch payments can be changed to draft state"""
        # matched?
        if self.filtered(lambda x: x.state != 'sent'):
            raise UserError("Only sent batch payments can be changed to draft state.")
        self.payment_ids.is_move_sent = False
        self.write({'state': 'draft'})

