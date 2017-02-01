# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def _create_analytic_account(self, prefix=None):
        for order in self:
            template = order.template_id.analytic_template_id
            projects = template.project_ids
            if projects and len(projects) == 1:
                name = order.name
                if prefix:
                    name = prefix + ": " + order.name
                default = {
                    'account_type': 'normal',
                    'name': name,
                    'code': order.client_order_ref,
                    'company_id': order.company_id.id,
                    'partner_id': order.partner_id.id
                }
                order.project_id = projects.copy(
                    default=default).analytic_account_id
