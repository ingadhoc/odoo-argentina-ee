# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
from openerp.tools.safe_eval import safe_eval as eval


class DatabaseType(models.Model):
    _inherit = "infrastructure.database_type"

    portal_visible = fields.Boolean(
    )
