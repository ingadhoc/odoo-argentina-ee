# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class SaleQuoteTemplate(models.Model):
    _inherit = "sale.quote.template"

    analytic_template_id = fields.Many2one(
        'account.analytic.account',
        'Analytic Template',
    )
