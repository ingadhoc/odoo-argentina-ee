from odoo import models, fields, api
import base64
import csv
from io import StringIO
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    riesgo_fiscal_csv_file = fields.Binary(string="CSV Riesgo Fiscal")
    riesgo_fiscal_csv_file_last_update = fields.Datetime(
        readonly=True,
    )

    @api.model
    def write(self, vals):
        if 'riesgo_fiscal_csv_file' in vals:
            vals['riesgo_fiscal_csv_file_last_update'] = fields.Datetime.now()
        return super(ResCompany, self).write(vals)

    def process_csv_file(self, partner_vat, activity_codes):
        if self.riesgo_fiscal_csv_file:
            # Decode the base64 file content and parse the CSV
            csv_content = base64.b64decode(self.riesgo_fiscal_csv_file)
            csv_data = StringIO(csv_content.decode('utf-8'))
            reader = csv.reader(csv_data, delimiter=';')
            actividades_con_riesgo = []
            actividades_con_alicuota_cero = []
            # Process each row in the CSV
            for row in reader:
                if partner_vat == row[0] and (row[3] in activity_codes):
                    if row[6] == 'A':
                        actividades_con_alicuota_cero.append(row[3])
                    if row[7] == 'S':
                        actividades_con_riesgo.append(row[3])
            return actividades_con_riesgo, actividades_con_alicuota_cero
        else:
            raise UserError('Debe subir el archivo de riesgo fiscal en la sección de ajustes de contabilidad para calcular la retención automática de Mendoza.')
