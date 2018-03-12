# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    phonecall_ids = fields.One2many(
        'crm.phonecall',
        'partner_id',
        'Phonecalls'
    )
    phonecall_count = fields.Integer(
        compute='compute_phonecall_count',
        string="Phonecalls",
    )

    @api.multi
    @api.depends('phonecall_ids')
    def compute_phonecall_count(self):
        for rec in self:
            rec.phonecall_count = len(rec.phonecall_ids)
