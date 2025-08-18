##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class DownloadFilesWizardLine(models.TransientModel):
    _inherit = "res.download_files_wizard_line"

    txt_filename = fields.Char(
        string="Filename"  # Changed string to "Filename" to allow downloading other file types
    )
