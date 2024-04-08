from odoo import models, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'

    codigo_regimen = fields.Char(string='Codigo de regimen IVA', size=3)
    porcentaje_exclusion = fields.Float(string='Porcentaje de exclusión')
    codigo_impuesto = fields.Selection([('01', 'Retención Ganancias'),
                                        ('02', 'Retención IVA'),
                                        ])
