##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    is_closed = fields.Boolean(
        'Closed for timesheet on tickets',
        help="Tickets with tasks on this stage will display a warning"
        " telling that task is closed.",
    )
