# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api
# from openerp.exceptions import UserError


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def invoice_cancel_from_done(self):
        for rec in self:
            if not rec.payment_move_line_ids and rec.state == 'paid':
                rec.action_cancel()
