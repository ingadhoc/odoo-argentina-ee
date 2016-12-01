# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class DatabaseType(models.Model):

    _inherit = 'infrastructure.database_type'

    is_production = fields.Boolean(
        help='Databases of this type are used to get data to invoice on '
        'contracts'
    )
