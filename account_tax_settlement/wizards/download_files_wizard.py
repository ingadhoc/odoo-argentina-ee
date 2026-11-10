##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64

from odoo import api, fields, models

# from odoo.exceptions import ValidationError


class DownloadFilesWizard(models.TransientModel):
    _name = "res.download_files_wizard"
    _description = "Wizard genérico para descargar archivos"

    line_ids = fields.One2many(
        "res.download_files_wizard_line",
        "wizard_id",
        "Files",
        readonly=True,
    )

    show_arba_warning = fields.Boolean(string="Show ARBA Warning", default=False)

    arba_warning_html = fields.Html(string="ARBA Warning", compute="_compute_arba_warning_html")

    notes_html = fields.Html(
        string="Notes",
        readonly=True,
        help="Data to keep in mind when filing the files, e.g. what has to be typed by hand in the tax portal.",
    )

    @api.depends("show_arba_warning")
    def _compute_arba_warning_html(self):
        for wizard in self:
            if wizard.show_arba_warning:
                wizard.arba_warning_html = self.env["ir.qweb"]._render(
                    "account_tax_settlement.arba_warning_template", {}
                )
            else:
                wizard.arba_warning_html = False

    @api.model
    def action_get_files(self, files_values, settlement_tax=None):
        """Open the wizard with the files to download.

        Each value has ``txt_filename`` and ``txt_content`` (text, or bytes for binary files like a ZIP), and may
        bring ``notes``, an HTML shown as a warning on top of the files.
        """
        has_arba = settlement_tax and (settlement_tax == "iibb_aplicado" or settlement_tax == "iibb_aplicado_act_7")

        wizard = self.env["res.download_files_wizard"].create(
            {
                "line_ids": [
                    (
                        0,
                        False,
                        {
                            "txt_filename": x["txt_filename"],
                            "txt_binary": base64.b64encode(
                                x["txt_content"]
                                if isinstance(x["txt_content"], bytes)
                                else x["txt_content"].encode("utf-8")
                            ),
                        },
                    )
                    for x in files_values
                    if x["txt_content"]
                ],
                "show_arba_warning": has_arba,
                "notes_html": "".join(x["notes"] for x in files_values if x.get("notes")) or False,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_id": wizard.id,
            "res_model": wizard._name,
            "view_mode": "form",
            "view_type": "form",
            "target": "new",
        }


class DownloadFileWizardLine(models.TransientModel):
    _name = "res.download_files_wizard_line"
    _description = "Wizard genérico para descargar archivos"

    wizard_id = fields.Many2one(
        "res.download_files_wizard",
    )
    txt_filename = fields.Char()
    txt_binary = fields.Binary()
