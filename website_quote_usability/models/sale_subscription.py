# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    @api.model
    def create(self, vals):
        if not vals.get('analytic_account_id', False):
            template_id = vals.get('template_id', False)
            template = self.browse(template_id)
            projects = template.project_ids
            if projects and len(projects) == 1:
                partner_id = vals.get('partner_id', False)
                company_id = vals.get('company_id', False)
                default = {
                    'account_type': 'normal',
                    'company_id': company_id,
                    'partner_id': partner_id
                }
                project = projects[0].copy(default=default)
                vals['analytic_account_id'] = project.analytic_account_id.id
        return super(SaleSubscription, self).create(vals)
