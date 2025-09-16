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
        # transformamos a binary y agregamos formato para campos o2m
        has_arba = settlement_tax and (settlement_tax == "iibb_aplicado" or settlement_tax == "iibb_aplicado_act_7")

        wizard = self.env["res.download_files_wizard"].create(
            {
                "line_ids": [
                    (
                        0,
                        False,
                        {
                            "txt_filename": x["txt_filename"],
                            "txt_binary": base64.b64encode(x["txt_content"].encode("utf-8")),
                        },
                    )
                    for x in files_values
                    if x["txt_content"]
                ],
                "show_arba_warning": has_arba,
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
