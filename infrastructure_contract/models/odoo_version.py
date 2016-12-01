# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class odoo_version(models.Model):

    _inherit = 'infrastructure.odoo_version'

    support_start_date = fields.Date(
        string='Support Start Date',
    )
    support_end_date = fields.Date(
        string='Support End Date',
    )
    support_end_notification_date = fields.Date(
        string='Support End Notification Date',
    )
