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
