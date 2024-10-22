from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sire_aplica_cdi = fields.Boolean(string='Aplica CDI',
                                     help="Campo para archivo txt Ganancias SIRE. Marcar si aplica CDI")
    sire_aplica_acrecentamiento = fields.Boolean(string='Aplica acrecentamiento',
                                                 help="Campo para archivo txt Ganancias SIRE. Marcar si aplica CDI")
    sire_codigo_alicuota = fields.Char(size=4)
    born_country_id = fields.Many2one('res.country', string='País de Nacimiento', ondelete='restrict')
    birthdate = fields.Date(string='Fecha de Nacimiento')
