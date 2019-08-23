# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in root directory
##############################################################################
from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)


class AccountJournalBookGroup(models.Model):
    _name = 'account.journal.book.group'
    _description = 'Account Journal Book Group'

    name = fields.Char(
        required=True,
    )


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    book_group_id = fields.Many2one(
        'account.journal.book.group',
        string='Book Group',
    )
