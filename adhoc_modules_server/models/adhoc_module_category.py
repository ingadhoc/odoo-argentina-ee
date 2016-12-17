# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api
import logging
_logger = logging.getLogger(__name__)


class AdhocModuleCategory(models.Model):
    _inherit = 'adhoc.module.category'
    _name = 'adhoc.module.category.server'

    product_tmpl_ids = fields.Many2many(
        'product.template',
        'adhoc_module_category_product_rel',
        'adhoca_category_id', 'product_tmpl_id',
        'Products',
    )
    module_ids = fields.One2many(
        'adhoc.module.module',
        'adhoc_category_id',
        'Modules',
        # domain=[('visible', '=', True)],
        readonly=False,
    )
    parent_id = fields.Many2one(
        'adhoc.module.category.server',
        'Parent Category',
        select=True,
        ondelete='restrict',
        readonly=False,
    )
    child_ids = fields.One2many(
        'adhoc.module.category.server',
        'parent_id',
        'Child Categories',
        readonly=False,
    )
    visibility = fields.Selection(
        readonly=False,
    )
    contracted_product = fields.Char(
        readonly=False,
    )
    name = fields.Char(
        readonly=False,
    )
    code = fields.Char(
        readonly=False,
    )
    description = fields.Text(
        readonly=False,
    )
    sequence = fields.Integer(
        readonly=False,
    )

    @api.multi
    def get_related_contracted_product(self, contract_id):
        """
        Function called from remote databases to get contracted products
        """
        self.ensure_one()
        analytic_lines = self.env[
            'sale.subscription.line'].sudo().search([
                ('analytic_account_id.analytic_account_id', '=', contract_id),
                ('product_id.product_tmpl_id', 'in',
                    self.product_tmpl_ids.ids),
            ])
        if analytic_lines:
            return analytic_lines.mapped('product_id.name')
        else:
            return False

    @api.multi
    def action_subcategories(self):
        self.ensure_one()
        action = self.env['ir.model.data'].xmlid_to_object(
            'adhoc_modules_server.action_adhoc_module_category')

        if not action:
            return False
        res = action.read()[0]
        # we clear root categories and we use parent in context
        # res['domain'] = [('parent_id', '=', self.id)]
        res['context'] = {
            'search_default_parent_id': self.id,
        }
        return res

    @api.multi
    def action_modules(self):
        self.ensure_one()
        action = self.env['ir.model.data'].xmlid_to_object(
            'adhoc_modules_server.action_adhoc_module_from_category')

        if not action:
            return False
        res = action.read()[0]
        res['domain'] = [('adhoc_category_id', '=', self.id)]

        return res
