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
        """ On creating a ticket, if not user is set, then we get if from
        _onchange_team_id """
        rec = super().create(vals)
        if not rec.user_id:
            rec._onchange_team_id()
        return rec

    @api.onchange('team_id', 'project_id')
    def _onchange_team_id(self):
        """ No lo hacemos en el metodo de team "def get_new_user(self)" porque
        el _onchange_team_id solo asigna si no tiene user, lo cual tiene
        sentido para los metodos nativo de odoo "aleatorio" y "balanceado",
        pero en estos casos nuevos que implementamos queremos que al cambiar de
        equipo, por mas que ya tenga user, sugiera un cambio de user.
        """
        super()._onchange_team_id()
        if self.team_id.assign_method == 'project_responsable':
            self.user_id = self.project_id.user_id
        elif self.team_id.assign_method == 'unassigned':
            self.user_id = False
        elif self.team_id.assign_method == 'specific_user':
            self.user_id = self.team_id.user_id

    @api.onchange('project_id')
    def _onchange_project(self):
        """ Bring default partner_id if ticket created from project """
        if self.project_id and self.project_id.partner_id:
            self.partner_id = self.project_id.partner_id
