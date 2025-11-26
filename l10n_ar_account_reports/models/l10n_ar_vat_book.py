# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10n_ArTaxReportHandler(models.AbstractModel):
    _inherit = "l10n_ar.tax.report.handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        export_buttons = [
            {
                "name": "Retenciones de IVA sufridas",
                "sequence": 30,
                "action": "export_file",
                "action_param": "ret_iva_sufridas_txt",
                "file_export_type": "TXT",
            },
            {
                "name": "Percepciones de IVA sufridas",
                "sequence": 30,
                "action": "export_file",
                "action_param": "perc_iva_sufridas_txt",
                "file_export_type": "TXT",
            },
        ]

        options["buttons"].extend(export_buttons)

    def ret_iva_sufridas_txt(self, options):
        return {
            "file_name": "Retenciones IVA Sufridas.txt",
            "file_content": self._misiones_book_get_txt_files(options),
            "file_type": "txt",
        }

    def perc_iva_sufridas_txt(self, options):
        return {
            "file_name": "Percepciones IVA Sufridas.txt",
            "file_content": self._misiones_book_get_txt_files(options),
            "file_type": "txt",
        }
