# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in root directory
##############################################################################
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    book_group_id = fields.Many2one(
        'account.journal.book.group',
        string='Journal Book Report',
    )
