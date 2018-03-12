##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval as eval


class DatabaseType(models.Model):
    _inherit = "infrastructure.database_type"

    portal_visible = fields.Boolean(
    )
