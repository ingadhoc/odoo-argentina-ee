from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    riesgo_fiscal_csv_file = fields.Binary(
        related='company_id.riesgo_fiscal_csv_file',
        readonly=False,
    )
    riesgo_fiscal_csv_file_last_update = fields.Datetime(
        related='company_id.riesgo_fiscal_csv_file_last_update',
        string="Última Modificación"
    )
