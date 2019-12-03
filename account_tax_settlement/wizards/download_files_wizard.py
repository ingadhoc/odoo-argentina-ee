##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64
from odoo import api, fields, models
# from odoo.exceptions import ValidationError


class DownloadFilesWizard(models.TransientModel):
    _name = 'download_files_wizard'
    _description = 'Wizard genérico para descargar archivos'

    line_ids = fields.One2many(
        'download_files_wizard_line',
        'wizard_id',
        'Files',
        readonly=True,
    )

    @api.model
    def action_get_files(self, files_values):
        # transformamos a binary y agregamos formato para campos o2m

        wizard = self.env['download_files_wizard'].create({
            'line_ids': [(0, False, {
                'txt_filename': x['txt_filename'],
                'txt_binary': base64.encodestring(
                    x['txt_content'].encode('utf-8')),
            }) for x in files_values if x['txt_content']],
        })

        return {
            'type': 'ir.actions.act_window',
            'res_id': wizard.id,
            'res_model': wizard._name,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
        }


class DownloadFileWizardLine(models.TransientModel):
    _name = 'download_files_wizard_line'
    _description = 'Wizard genérico para descargar archivos'

    wizard_id = fields.Many2one(
        'download_files_wizard',
    )
    txt_filename = fields.Char(
    )
    txt_binary = fields.Binary(
    )
