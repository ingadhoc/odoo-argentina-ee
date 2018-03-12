# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class SaleSubscriptionLine(models.Model):
    _inherit = 'sale.subscription.line'
    _order = 'sequence'

    sequence = fields.Integer(
        'Sequence',
        required=True,
        default=10,
        help="The sequence field is used to order lines"
    )
