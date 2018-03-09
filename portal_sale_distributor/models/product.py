# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    standard_price = fields.Float(
        groups='base.group_user,\
        portal_sale_distributor.group_portal_distributor')
