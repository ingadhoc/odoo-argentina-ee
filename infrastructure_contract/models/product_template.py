# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields
import logging

_logger = logging.getLogger(__name__)


class ProductTempalte(models.Model):
    _inherit = 'product.template'

    contracted_quantity_expression = fields.Text(
        help='Expression to evaluate quantity on a contract for a customer '
        'database. It must return a float',
    )
    installation_command = fields.Text(
        help='Expression to be run on database installation. Return will be'
        ' appended like a message'
    )
