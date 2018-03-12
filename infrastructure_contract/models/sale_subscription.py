# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    infra_database_ids = fields.One2many(
        'infrastructure.database',
        'contract_id',
        'Databases',
    )
    infra_database_count = fields.Integer(
        string='# Databases',
        compute='_get_databases'
    )
    odoo_version_id = fields.Many2one(
        'infrastructure.odoo_version', string='Odoo Version')
    support_validity = fields.Date(
        related='odoo_version_id.support_end_date',
        string="Support Validity",
        readonly=True,
        store=True,
    )

    @api.one
    @api.depends('infra_database_ids')
    def _get_databases(self):
        self.infra_database_count = len(self.infra_database_ids)

    @api.one
    @api.constrains('state', 'infra_database_ids')
    def check_databases_state(self):
        not_inactive_dbs = self.infra_database_ids.filtered(
            lambda x: x.state != 'inactive')
        if self.state == 'close' and not_inactive_dbs:
            raise ValidationError(_(
                'You can not close a contract if there are related dbs in '
                'other state than "inactive".\n'
                '* DBS: %s') % not_inactive_dbs.ids)

    @api.multi
    def get_main_database(self):
        prod_dbs = self.infra_database_ids.filtered(
            lambda x: x.instance_type_id.is_production and x.state == 'active')
        if len(prod_dbs) > 1:
            raise ValidationError(_(
                'More than one production database linked to contract %s!') % (
                self.name))
        elif len(prod_dbs) == 0:
            raise ValidationError(_(
                'No production database linked to contract %s!') % (
                self.name))
        return prod_dbs

    @api.multi
    def update_remote_contracted_products(self):
        for contract in self:
            contract.get_main_database().update_remote_contracted_products()

    @api.multi
    def run_installation_command_on_remote_database(self):
        for contract in self:
            contract.get_main_database(
            ).run_installation_command_on_remote_database()

    @api.multi
    def update_lines_data_from_database(self):
        for contract in self:
            contract.get_main_database().update_contract_data_from_database()

    @api.multi
    def action_view_databases(self):
        '''
        This function returns an action that display a form or tree view
        '''
        self.ensure_one()
        databases = self.infra_database_ids
        action = self.env['ir.model.data'].xmlid_to_object(
            'infrastructure.action_infrastructure_database_databases')

        if not action:
            return False
        res = action.read()[0]
        if len(self) == 1:
            res['context'] = {
                # 'default_instance_id': self.id,
                # 'search_default_instance_id': self.id,
                'search_default_contract_id': self.id,
                'search_default_not_inactive': 1,
            }
        if not len(databases.ids) > 1:
            form_view_id = self.env['ir.model.data'].xmlid_to_res_id(
                'infrastructure.view_infrastructure_database_form')
            res['views'] = [(form_view_id, 'form')]
            # if 1 then we send res_id, if 0 open a new form view
            res['res_id'] = databases and databases.ids[0] or False
        return res
