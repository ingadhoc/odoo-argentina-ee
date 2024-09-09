from odoo import models


class AccountTax(models.Model):
    _inherit = "account.tax"

    def get_partner_alicuot(self, partner, date, line=None):
        """ La alícuota para el archivo txt de mendoza que se genera desde el método iibb_aplicado_sircar_files_values
        no se obtiene del partner sino que se obtiene del payment, y el código de régimen se obtiene del impuesto pero
        extendemos el método get_partner_alicuot original para usarlo como puente, agregamos 'line' como parámentro. """
        if line and line.payment_id and line.payment_id.alicuota_mendoza and line.payment_id.tax_withholding_id.codigo_regimen:
            return self.env['res.partner.arba_alicuot'].new({'alicuota_retencion': line.payment_id.alicuota_mendoza * 100, 'partner_id': partner, 'regimen_retencion': line.payment_id.tax_withholding_id.codigo_regimen})
        return super().get_partner_alicuot(partner, date, line=line)
