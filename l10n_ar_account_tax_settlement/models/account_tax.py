from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AccountTax(models.Model):
    _inherit = 'account.tax'

    codigo_regimen = fields.Char(string='Codigo de regimen IVA', size=3)
    porcentaje_exclusion = fields.Float(string='Porcentaje de exclusión')

    @api.depends('withholding_advances')
    def withholding_advances_misiones(self):
        """ Los impuestos de retención de Misiones no deben tener en cuenta para su cálculo otras retenciones que se hicieron en el período """
        if self.withholding_advances and self.tax_group_id.name == 'Retención IIBB Misiones':
            raise ValidationError("Lo impuestos de retención de Misiones no pueden tener seleccionada la opción de Adelantos Sujetos a Retención ya que su cálculo no debe tener en cuenta otras retenciones realizadas en el período.")
