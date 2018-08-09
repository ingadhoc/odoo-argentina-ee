##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api


class HelpdeskTeam(models.Model):

    _inherit = 'helpdesk.team'

    @api.constrains('use_helpdesk_timesheet', 'project_id')
    def project_allow_tickets(self):
        """ If use_helpdesk_timesheet then set the related project to
        allow_tickets
        """
        projects = self.filtered('use_helpdesk_timesheet').mapped(
            'project_id')
        if projects:
            projects.write({'allow_tickets': True})
