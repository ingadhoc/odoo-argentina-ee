# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AdhocModuleModule(models.Model):
    _inherit = 'ir.module.module'
    _name = 'adhoc.module.module'

    @api.one
    @api.constrains('incompatible_module_ids')
    def change_incompatible_module_ids(self):
        if self._context.get('stop'):
            return True
        if self in self.incompatible_module_ids:
            raise ValidationError(_('Can be incompatible with same module'))
        # update modules that are not more incompatible
        no_more = self.search([
            ('incompatible_module_ids', 'in', [self.id]),
        ])
        no_more -= self.incompatible_module_ids
        no_more -= self
        no_more.write({'incompatible_module_ids': [(3, self.id, _)]})

        # update new incompatible
        self.incompatible_module_ids.with_context(stop=True).write(
            {'incompatible_module_ids': [(4, self.id, _)]})

    @api.one
    @api.depends('incompatible_module_ids')
    def _compute_incompatible_modules(self):
        if not self.incompatible_module_ids:
            res = False
        else:
            res = "['%s']" % (("','").join(
                self.incompatible_module_ids.mapped('name')))
        self.incompatible_modules = res

    incompatible_modules = fields.Char(
        # readonly=False,
        compute='_compute_incompatible_modules',
        store=True,
    )
    incompatible_module_ids = fields.Many2many(
        'adhoc.module.module',
        'adhoc_module_module_incompatible_rel',
        'module1_id', 'module2_id',
        compute=False,
        # compute='compute_incompatible_modules',
    )
    state = fields.Selection(
        default=False,
    )
    adhoc_category_id = fields.Many2one(
        'adhoc.module.category.server',
        'ADHOC Category',
        auto_join=True,
        readonly=False,
    )
    repository_id = fields.Many2one(
        'adhoc.module.repository',
        'Repository',
        ondelete='cascade',
        required=True,
        auto_join=True,
        readonly=True,
    )
    dependencies_id = fields.One2many(
        'adhoc.module.dependency',
        'module_id',
        'Dependencies',
        readonly=True,
    )
    computed_summary = fields.Char(
        readonly=False,
    )
    adhoc_summary = fields.Char(
        readonly=False,
    )
    technically_critical = fields.Boolean(
        readonly=False,
    )
    adhoc_description_html = fields.Html(
        readonly=False,
    )
    support_type = fields.Selection(
        readonly=False,
        required=True,
    )
    review = fields.Selection(
        readonly=False,
    )
    conf_visibility = fields.Selection(
        readonly=False,
        required=True,
        default='to_review',
    )
    visibility_obs = fields.Char(
        readonly=False,
    )
    version = fields.Selection(
        related='repository_id.branch',
        readonly=True,
        store=True,
    )
    also_available_ids = fields.Many2many(
        'adhoc.module.module',
        compute='_compute_also_availables',
        string='Also available',
    )

    # modificamos esta contrain para poder tener nombre duplicado en != vers.
    # tal vez en el futuro necesitemos permitir igual nombre, por ejemplo
    # cuando sobreescribimos algun modulo
    _sql_constraints = [
        ('name_uniq', 'unique (name, version)',
            """Name must be unique per odoo version!"""),
    ]

    @api.multi
    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, '%s (%s)' % (rec.name, rec.version)))
        return res

    @api.multi
    def copy_data_from_also_available(self):
        for rec in self:
            if not rec.also_available_ids:
                continue
            from_rec = rec.also_available_ids[0]
            fields = [
                'adhoc_category_id',
                'conf_visibility',
                'review',
                'technically_critical',
                'support_type',
                'sequence',
                'incompatible_modules',
            ]
            for field in fields:
                rec.update({field: from_rec[field]})

    @api.depends('name')
    def _compute_also_availables(self):
        for rec in self:
            rec.also_available_ids = rec.search([
                ('name', '=', rec.name),
                # cann ot use .id because of oncreation
                # ('id', '!=', rec.id),
            ]) - rec

    @api.onchange('conf_visibility')
    def change_conf_visibility(self):
        if self.conf_visibility == 'auto_install_by_code':
            raise ValidationError(_(
                'You can not set visibility "auto_install_by_code"'))

    @api.model
    def create(self, vals):
        # ir module modifies create, we need default one
        create_original = models.BaseModel.create
        module = create_original(self, vals)
        # if we are on install_mode, ids are already loaded
        if self._context.get('install_mode'):
            return module
        module_metadata = {
            'name': 'module_%s_%s' % (
                vals['name'],
                module.repository_id.branch.replace('.', '_')),
            'model': self._name,
            'module': 'adhoc_module_server',
            'res_id': module.id,
            'noupdate': True,
        }
        self.env['ir.model.data'].create(module_metadata)
        return module

    @api.multi
    def _update_dependencies(self, depends=None):
        self.ensure_one()
        if depends is None:
            depends = []
        existing = set(x.name for x in self.dependencies_id)
        needed = set(depends)
        for dep in (needed - existing):
            self._cr.execute(
                'INSERT INTO adhoc_module_dependency (module_id, name) '
                'values (%s, %s)', (self.id, dep))
        for dep in (existing - needed):
            self._cr.execute(
                'DELETE FROM adhoc_module_dependency WHERE module_id = %s '
                'and name = %s', (self.id, dep))
        self.invalidate_cache(['dependencies_id'])

    @api.multi
    def open_module(self):
        self.ensure_one()
        module_form = self.env.ref(
            'adhoc_modules_server.view_adhoc_module_module_form', False)
        if not module_form:
            return False
        return {
            'name': _('Module Description'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'adhoc.module.module',
            'views': [(module_form.id, 'form')],
            'view_id': module_form.id,
            'res_id': self.id,
            'target': 'current',
            'target': 'new',
            'context': self._context,
            # top open in editable form
            'flags': {
                'form': {'action_buttons': True, 'options': {'mode': 'edit'}}}
        }
