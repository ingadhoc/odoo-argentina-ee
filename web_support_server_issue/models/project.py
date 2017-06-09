# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api
import logging
_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = "project.project"

    # MOVED to saas provider
    # subscription_ids = fields.One2many(
    #     # 'sale.subscription',
    #     related='analytic_account_id.subscription_ids',
    #     string='Subscriptions',
    # )
    # subscription_count = fields.Integer(
    #     related='analytic_account_id.subscription_count',
    # )
    # database_ids = fields.One2many(
    #     'infrastructure.database',
    #     compute='_compute_databases'
    #     'Databases',
    # )
    # database_count = fields.Integer(
    #     string='# Databases',
    #     compute='_compute_databases'
    # )

    # @api.one
    # @api.depends('analytic_account_id')
    # def _compute_databases(self):
    #     databases = self.analytic_account_id.subscription_ids.mapped(
    #         'infra_database_ids')
    #     self.database_count = len(databases)
    #     self.database_ids = databases

    # @api.multi
    # def action_view_databases(self):
    #     subs = self.analytic_account_id.subscription_ids
    #     return subs and subs[0].action_view_databases() or False

    # @api.multi
    # def subscriptions_action(self):
    #     return self.analytic_account_id.subscriptions_action()
