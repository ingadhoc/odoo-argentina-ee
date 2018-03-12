# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api

DEP_STATES = [
    ('uninstallable', 'Uninstallable'),
    ('uninstalled', 'Not Installed'),
    ('installed', 'Installed'),
    ('to upgrade', 'To be upgraded'),
    ('to remove', 'To be removed'),
    ('to install', 'To be installed'),
    ('unknown', 'Unknown'),
]


class AdhocModuleDependency(models.Model):
    _name = "adhoc.module.dependency"
    _description = "Module dependency"

    # the dependency name
    name = fields.Char(
        index=True
    )
    # the module that depends on it
    module_id = fields.Many2one(
        'adhoc.module.module',
        'Module',
        ondelete='cascade',
        auto_join=True,
    )
    # the module corresponding to the dependency, and its status
    depend_id = fields.Many2one(
        'adhoc.module.module',
        'Dependency',
        compute='_compute_depend'
    )
    state = fields.Selection(
        DEP_STATES,
        string='Status',
        compute='_compute_depend'
    )

    @api.one
    @api.depends('name')
    def _compute_depend(self):
        mod = self.env['adhoc.module.module'].search([
            ('name', '=', self.name),
            ('repository_id.branch', '=', self.module_id.repository_id.branch),
        ], limit=1)
        self.depend_id = mod
        self.state = self.depend_id.state or 'unknown'
