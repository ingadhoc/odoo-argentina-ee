# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in root directory
##############################################################################
from odoo import fields, models


class AccountJournalBookGroup(models.Model):
    _name = 'account.journal.book.group'
    _description = 'Account Journal Book Group'

    name = fields.Char(
        required=True,
    )
