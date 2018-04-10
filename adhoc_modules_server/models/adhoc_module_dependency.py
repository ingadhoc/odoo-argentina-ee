##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api

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

    @api.depends('name')
    def _compute_depend(self):
        for record in self:
            mod = self.env['adhoc.module.module'].search([
                ('name', '=', record.name),
                ('repository_id.branch', '=',
                 record.module_id.repository_id.branch),
            ], limit=1)
            record.depend_id = mod
            record.state = record.depend_id.state or 'unknown'
