# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProductTempalte(models.Model):
    _inherit = 'product.template'

    contract_sequence = fields.Integer(
        string='Contract Sequence',
        help='This sequence will be used to order lines on contract',
        default=10,
        required=True,
    )
    contract_type = fields.Selection([
        ('app', 'App'),
        ('requirement', 'Requirement'),
    ],
        string='Contract Type',
    )
    adhoc_category_ids = fields.Many2many(
        'adhoc.module.category.server',
        'adhoc_module_category_product_rel',
        'product_tmpl_id', 'adhoca_category_id',
        string='Categories',
    )
    # TODO en realidad esta dependencia deberia ser en clase product
    # product
    adhoc_product_dependency_ids = fields.Many2many(
        'product.template',
        'product_adhoc_depedency_rel',
        'product_tmpl_id', 'product_tmpl_dependency_id',
        string='Dependencies',
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    contract_quantity = fields.Integer(
        compute='_compute_contract_data',
        inverse='_set_contract_quantity',
    )
    contract_state = fields.Selection([
        ('contracted', 'contracted'), ('un_contracted', 'un_contracted')
    ],
        'Contract State',
        compute='_compute_contract_data',
    )

    @api.multi
    def _set_contract_quantity(self):
        contract = self._get_contract()
        if not contract:
            return False
        self._add_to_contract(contract)

    @api.multi
    def _compute_contract_data(self):
        contract = self._get_contract()
        if not contract:
            return False
        for product in self:
            # we use filtered instead of compute because of cache
            if contract._name == 'sale.order':
                lines = contract.order_line.filtered(
                    lambda x: x.product_id == product)
            elif contract._name == 'sale.subscription':
                lines = contract.recurring_invoice_line_ids.filtered(
                    lambda x: x.product_id == product)
            # if requirement, we want quantity, else, yes, no
            if product.contract_type == 'requirement':
                product.contract_quantity = (
                    lines and lines[0].quantity or False)
            else:
                if lines:
                    product.contract_state = 'contracted'
                else:
                    product.contract_state = 'un_contracted'

    @api.multi
    def _add_to_contract(self, contract):
        if contract._name == 'sale.order':
            contract_line = self.env['sale.order.line']
            parent_field = 'order_id'
        elif contract._name == 'sale.subscription':
            contract_line = self.env['sale.subscription.line']
            parent_field = 'analytic_account_id'
        partner = contract.partner_id
        pricelist = contract.pricelist_id
        company = contract.company_id
        for product in self:
            if product.contract_type == 'requirement':
                quantity = product.contract_quantity
            else:
                quantity = 1.0

            line = contract_line.search([
                (parent_field, '=', contract.id),
                ('product_id', '=', product.id)], limit=1)
            # just in case quantity is zero
            if line:
                line.quantity = quantity
            else:
                if contract._name == 'sale.order':
                    contract_line = contract_line.create({
                        'order_id': contract.id,
                        'product_uom_qty': quantity,
                        'product_id': product.id,
                    })
                    # contract_line.product_id_change()
                elif contract._name == 'sale.subscription':
                    vals = contract_line.product_id_change(
                        product.id, False, qty=quantity,
                        name=False, partner_id=partner.id, price_unit=False,
                        pricelist_id=pricelist.id, company_id=company.id).get(
                        'value', {})
                    # we create only with mandatory fields
                    contract_line = contract_line.create({
                        parent_field: contract.id,
                        'product_id': product.id,
                        'name': vals.pop('name'),
                        'price_unit': vals.pop('price_unit'),
                        'uom_id': vals.pop('uom_id'),
                    })
                    # we use setattr instead of write so tax_id m2m field can be
                    # setted and also because other modules can add more fields
                    for k, v in vals.iteritems():
                        setattr(contract_line, k, v)
            dep_prods = product.adhoc_product_dependency_ids.mapped(
                'product_variant_ids')
            dep_prods._add_to_contract(contract)

    @api.multi
    def _remove_from_contract(self, contract):
        if contract._name == 'sale.order':
            contract_line = self.env['sale.order.line']
            parent_field = 'order_id'
        elif contract._name == 'sale.subscription':
            contract_line = self.env['sale.subscription.line']
            parent_field = 'analytic_account_id'
        for product in self:
            contract_line.search([
                (parent_field, '=', contract.id),
                ('product_id', '=', product.id)]).unlink()
            upper_prods = self.search([(
                'adhoc_product_dependency_ids',
                '=',
                product.product_tmpl_id.id)])
            upper_prods._remove_from_contract(contract)

    @api.model
    def _get_contract(self):
        contract_id = self._context.get('active_id')
        model = self._context.get('active_model')
        # on tree editable, we get from params
        if not contract_id or model != 'sale.subscription':
            params = self._context.get('params', False)
            if params:
                contract_id = params.get('id')
                model = params.get('model')
        if not contract_id or model not in ['sale.subscription', 'sale.order']:
            return False
        return self.env[model].browse(contract_id)

    @api.multi
    def action_add_to_contract(self):
        contract = self._get_contract()
        if not contract:
            return False
        self._add_to_contract(contract)

    @api.multi
    def action_remove_to_contract(self):
        contract = self._get_contract()
        if not contract:
            return False
        self._remove_from_contract(contract)
