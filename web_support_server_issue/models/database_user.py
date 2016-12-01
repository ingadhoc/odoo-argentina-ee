# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api
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
