##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, _
from odoo.exceptions import ValidationError


class HelpdeskTicket(models.Model):

    _inherit = 'helpdesk.ticket'

    @api.constrains('stage_id')
    def validate_ticket(self):
        for ticket in self.filtered(lambda x: x.stage_id.is_close):
            if ticket.task_id.stage_id.is_closed:
                raise ValidationError(_(
                    "You can not close a ticket with active task, we consider"
                    " active task the one in stages without option 'closed'"
                    ' (ticket ID %s)' % (ticket.id)))

    @api.model
    def create(self, vals):
        """ On creating a ticket, if not user is set, then we get if from team
        if assign_method == 'project_responsable'
        """
        rec = super(HelpdeskTicket, self).create(vals)
        if not rec.user_id:
            rec.set_responsable_from_project()
        return rec

    @api.onchange('team_id', 'project_id')
    def set_responsable_from_project(self):
        if self.team_id.assign_method == 'project_responsable':
            self.user_id = self.project_id.user_id

    @api.onchange('team_id')
    def _onchange_team_id(self):
        super(HelpdeskTicket, self)._onchange_team_id()
        if self.team_id.assign_method == 'unassigned':
            self.user_id = False
