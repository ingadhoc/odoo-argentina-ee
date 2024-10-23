from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    actividades_padron = fields.Many2many(
        'afip.activity',
        related='partner_id.actividades_padron',
    )
    activities_mendoza_ids = fields.Many2many(
        comodel_name='afip.activity',
        string="Activities in Mendoza",
        domain="[('id', 'in', actividades_padron)]"
    )
