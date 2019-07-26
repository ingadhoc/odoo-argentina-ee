##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class HelpdeskTeam(models.Model):

    _inherit = 'helpdesk.team'

    assign_method = fields.Selection(
        selection_add=[
            ("project_responsable", "Project Responsable"),
            ("specific_user", "Specific User"),
            ("unassigned", "Unassigned"),
        ])

    user_id = fields.Many2one(
        'res.users',
        'Specific user',
        domain=lambda self: [
            ('groups_id', 'in', self.env.ref(
                'helpdesk.group_helpdesk_user').id)],
    )

    @api.constrains('assign_method', 'member_ids')
    def _check_member_assignation(self):
        if not self.member_ids and self.assign_method in [
                'randomly', 'balanced']:
            raise ValidationError(_(
                "You must have team members assigned to change the "
                "assignation method."))

    @api.constrains('use_helpdesk_timesheet', 'project_id')
    def project_allow_tickets(self):
        """ If use_helpdesk_timesheet then set the related project to
        allow_tickets
        """
        projects = self.filtered('use_helpdesk_timesheet').mapped(
            'project_id')
        if projects:
            projects.write({'allow_tickets': True})
