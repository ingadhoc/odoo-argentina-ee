from odoo import models, fields
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):

    _inherit = "account.payment"

    # IMPORTANTE: alicuota_mendoza se guarda al momento de correr el código python del impuesto 'Retención IIBB Mendoza Aplicada' --> payment.write({'alicuota_mendoza': alicuota}). Ver por interfaz.
    alicuota_mendoza = fields.Float(help="Guardamos la alícuota para el txt de mendoza.", readonly=True)

    def compute_withholdings(self):
        """ Para el cálculo de retenciones automáticas de aplicadas de Mendoza siempre tiene que haber una factura vinculada al payment. Además debemos guardar en el payment de mendoza la alícuota aplicada. """
        res = super().compute_withholdings()
        tax_group_mendoza_id = self.env.ref('l10n_ar.tax_group_withholding_vat').id
        payment_mendoza = self.payment_ids.filtered(lambda x: x.tax_withholding_id.tax_group_id.id == tax_group_mendoza_id and x.tax_withholding_id.withholding_type == 'code' and x.state == 'draft')
        if payment_mendoza:
            if not self.to_pay_move_line_ids:
                raise ValidationError('No puede calcular retenciones automáticas de aplicadas de Mendoza si no seleccionó una factura para pagar')
            # Agregamos la alícuota de mendoza al payment (es necesario para generar el txt iibb_aplicado_sircar_files_values)
            payment_mendoza.alicuota_mendoza = self.alicuota_mendoza
        return res
