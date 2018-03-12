# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    copy_contract_description = fields.Boolean(
        'Copy Contract Description',
        help="Copy Contract description to recurring invoices")
