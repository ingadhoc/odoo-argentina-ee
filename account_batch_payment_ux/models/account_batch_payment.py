from odoo import models, fields, api, _
from odoo.exceptions import UserError, RedirectWarning


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
        matched_entries = self.payment_ids.filtered('is_matched')
        if matched_entries:
            error_msg = ("The following payments are reconciled and cannot be reset to draft state: \n")
            for entry in matched_entries:
                error_msg += f"{entry.name} \n"
            action_error = {
                'view_mode': 'tree',
                'name': _('Matched Entries'),
                'res_model': 'account.bank.statement.line',
                'type': 'ir.actions.act_window',
                'domain': [('id', 'in', matched_entries.mapped('reconciled_statement_line_ids').ids)],
                'views': [
                    (self.env.ref('account_accountant.view_bank_statement_line_kanban_bank_rec_widget').id, 'kanban'),
                    (self.env.ref('account_accountant.view_bank_statement_line_tree_bank_rec_widget').id, 'list'),
                ]
            }
            raise RedirectWarning(error_msg, action_error, _('Show matched entries'))   

        self.payment_ids.is_move_sent = False
        self.write({'state': 'draft'})
