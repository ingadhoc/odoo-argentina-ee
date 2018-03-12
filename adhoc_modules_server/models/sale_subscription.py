##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    apps_product_ids = fields.One2many(
        'product.product',
        string='Apps',
        compute='_compute_products',
    )
    requirements_product_ids = fields.One2many(
        'product.product',
        string='Requirements',
        compute='_compute_products',
        inverse='_dummy_inverse'
    )
    # product_categ_id = fields.Many2one(
    #     'product.category',
    #     'Modules Category',
    # )
    recurring_invoice_line_copy_ids = fields.One2many(
        related='recurring_invoice_line_ids',
        readonly=True,
    )

    @api.multi
    def _dummy_inverse(self):
        # dummy inverse to allow setting quantities
        return True

    @api.multi
    def select_contract_products(self):
        self.ensure_one()
        view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'adhoc_modules_server.product_product_kanban_view')
        return {
            'name': _('Products'),
            'view_type': 'form',
            "view_mode": 'kanban',
            'res_model': 'product.product',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.apps_product_ids.ids)],
            'view_id': view_id,
        }

    @api.multi
    # @api.depends('product_categ_id')
    def _compute_products(self):
        for contract in self:
            # if contract.product_categ_id:
            base_domain = [
                # ('categ_id', '=', contract.product_categ_id.id)
            ]
            contract.apps_product_ids = self.env[
                'product.product'].search(
                    base_domain + [('contract_type', '=', 'app')])
            contract.requirements_product_ids = self.env[
                'product.product'].search(
                    base_domain + [('contract_type', '=', 'requirement')])
