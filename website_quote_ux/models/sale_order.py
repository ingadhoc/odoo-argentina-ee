##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models


class SaleOrder(models.Model):

    _inherit = 'sale.order'

    @api.multi
    def open_quotation(self):
        res = super(SaleOrder, self).open_quotation()
        res.update({
            'target': 'new',
        })
        return res
