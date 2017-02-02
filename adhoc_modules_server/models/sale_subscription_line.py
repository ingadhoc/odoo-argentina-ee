# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields
import logging

_logger = logging.getLogger(__name__)


class SaleSubscriptionLine(models.Model):
    _inherit = 'sale.subscription.line'
    _order = 'sequence'

    implemented = fields.Boolean(
        'Implementado',
        help='Este producto a sido implementado por nosotros y debe tener '
        'garantia'
    )
    sequence = fields.Integer(
        related='product_id.contract_sequence',
        store=True,
        readonly=True,
    )

    _sql_constraints = [(
        'product_uniq',
        'unique (product_id, analytic_account_id)',
        'Product muts be unique per contract!')
    ]

    # @api.multi
    # def product_id_change(
    #         self, product, uom_id, qty=0, name='', partner_id=False,
    #         price_unit=False, pricelist_id=False, company_id=None):
    #     """
    #     Add product sequence
    #     """
    #     result = super(SaleSubscriptionLine, self).product_id_change(
    #         product, uom_id, qty=qty, name=name, partner_id=partner_id,
    #         price_unit=price_unit, pricelist_id=pricelist_id,
    #         company_id=company_id)
    #     result['value']['sequence'] = self.env['product.product'].browse(
    #         product).contract_sequence
    #     return result
