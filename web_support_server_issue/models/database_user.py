# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)


class database_user(models.Model):
    _inherit = "infrastructure.database.user"

    authorized_for_issues = fields.Boolean(
        'Authorized For Issues?'
    )

    @api.onchange('partner_id')
    def change_partner_id(self):
        if not self.partner_id:
            self.authorized_for_issues = False
