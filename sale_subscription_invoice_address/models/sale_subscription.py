##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields


class SaleSubscription(models.Model):

    _inherit = "sale.subscription"

    partner_invoice_id = fields.Many2one(
        'res.partner',
        string='Invoice Address',
        help="Invoice address for new invoices.",
    )

    @api.multi
    def _prepare_invoice_data(self):
        """ Copy the terms and conditions of the subscription as part of the
        invoice note.
        """
        self.ensure_one()
        res = super(SaleSubscription, self)._prepare_invoice_data()
        if self.partner_invoice_id:
            res.update({'partner_id': self.partner_invoice_id.id})
        return res
