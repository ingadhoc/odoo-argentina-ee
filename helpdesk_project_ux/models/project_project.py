##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    allow_tickets = fields.Boolean("Allow tickets", default=False)

    @api.constrains('active')
    def validate_active_from_tickets(self):
        for project in self.filtered(lambda x: not x.active and x.ticket_ids):
            open_tickets = project.ticket_ids.filtered(
                lambda x: not x.stage_id.fold)
            if open_tickets:
                raise ValidationError(
                    _("You can not close a project with active tickets,"
                      " we consider active ticket the one in stages "
                      "without option 'folded' (ticket IDs %s)" %
                      open_tickets.ids))

    @api.multi
    def write(self, vals):
        """ When project.project status active/archived change also apply
        to its tickets.
        """
        res = super(ProjectProject, self).write(vals)
        if 'active' in vals:
            self.with_context(active_test=False).mapped('ticket_ids').write({
                'active': vals['active']})
        return res
