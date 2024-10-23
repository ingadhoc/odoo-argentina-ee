from odoo import models, fields
from odoo.exceptions import UserError


class AfipActivity(models.Model):
    _inherit = "afip.activity"

    alicuota_general = fields.Char()
    posee_tasa_cero = fields.Char()
    no_posee_certificado_tasa_cero = fields.Char()

    def menor_alicuota(self, actividades_con_alicuota_cero):
        """Método utilizado para el cálculo de la menor alícuota a aplicar para 'Retención IIBB Mendoza Aplicada'."""
        aliquots = []
        activity_codes = self.mapped('code')
        activities = self.env['afip.activity'].search([('code', 'in', activity_codes)])
        activities_with_aliquots = activities.filtered(lambda x: x.alicuota_general or x.posee_tasa_cero or x.no_posee_certificado_tasa_cero)
        if not activities_with_aliquots:
            raise UserError('No hay actividades con alícuotas')
        actividades_con_alic = activities_with_aliquots.mapped('code')
        elementos_no_en_ambas = [activity for activity in activity_codes if activity not in actividades_con_alic]
        if elementos_no_en_ambas:
            raise UserError('Hay actividades en la factura que no tienen alícuota. Actividades: %s' % (','.join(elementos_no_en_ambas)))
        for code in activities_with_aliquots:
            if code.alicuota_general:
                aliquots.append((code.code, float(code.alicuota_general)))
            elif code.posee_tasa_cero and code.code in actividades_con_alicuota_cero:
                aliquots.append((code.code, float(code.posee_tasa_cero)))
            elif code.no_posee_certificado_tasa_cero:
                aliquots.append((code.code, float(code.no_posee_certificado_tasa_cero)))
        if not aliquots:
            raise UserError('Las actividades incluidas en la factura no tienen alícuota')
        # Busco la menor alícuota
        min_aliquot = min(aliquots, key=lambda x: x[1])
        return min_aliquot
