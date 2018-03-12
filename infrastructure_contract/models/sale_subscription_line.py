# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class SaleSubscriptionLine(models.Model):
    _inherit = 'sale.subscription.line'

    db_quantity = fields.Float(
        'Db Qty',
        help='Quantity readed on remote database',
        readonly=True,
    )
