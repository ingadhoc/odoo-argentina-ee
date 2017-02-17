# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields
# from openerp.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    unreconciled_adl_ids = fields.One2many(
        'account.debt.line',
        'partner_id',
        domain=[
            ('reconciled', '=', False),
            ('account_id.deprecated', '=', False),
            ('account_id.internal_type', '=', 'receivable')]
    )
