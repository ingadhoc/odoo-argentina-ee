##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class AccountPaymentGroup(models.Model):

    _inherit = "account.payment.group"

    # IMPORTANTE: alicuota_mendoza se guarda al momento de correr el código python del impuesto 'Retención IIBB Mendoza Aplicada' --> payment.write({'alicuota_mendoza': alicuota}). Ver por interfaz.
    alicuota_mendoza = fields.Float(help="Guardamos la alícuota para el txt de mendoza.", readonly=True)

    def compute_withholdings(self):
        """Para el cálculo de retenciones automáticas de aplicadas de Mendoza siempre tiene que haber una factura vinculada al payment group."""
        tax_group_mendoza_id = self.env.ref('l10n_ar_ux.tax_group_retencion_iibb_za').id
        retencion_mdza_aplicada = self.env['account.tax'].with_context(type=None).search([
                ('type_tax_use', '=', self.partner_type),
                ('company_id', '=', self.company_id.id),
                ('tax_group_id', '=', tax_group_mendoza_id),
            ], limit=1)
        if retencion_mdza_aplicada and not self.to_pay_move_line_ids:
            raise ValidationError('No puede calcular retenciones automáticas de aplicadas de Mendoza si no seleccionó una factura para pagar')
        else:
            super().compute_withholdings()

        # Agregamos la alícuota de mendoza al payment (es necesario para generar el txt iibb_aplicado_sircar_files_values)
        mendoza_tax_group_id = self.env.ref('l10n_ar_ux.tax_group_retencion_iibb_za').id
        payment_mendoza = self.payment_ids.filtered(lambda x: x.tax_withholding_id.tax_group_id.id == mendoza_tax_group_id and x.tax_withholding_id.withholding_type == 'code' and x.state == 'draft')
        if payment_mendoza:
            payment_mendoza.alicuota_mendoza = self.alicuota_mendoza
