# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import _, fields, models
from odoo.exceptions import RedirectWarning, UserError

from .helpers import get_standard_lines_domain


class L10n_ArIvaReportHandler(models.AbstractModel):
    _name = "l10n_ar.iva.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "IVA Sufrido Report Custom Handler"

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
                "branch_allowed": True,
            },
            {
                "name": "Percepciones de IVA sufridas",
                "sequence": 30,
                "action": "export_file",
                "action_param": "perc_iva_sufridas_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
        ]

        options["buttons"].extend(export_buttons)

    def ret_iva_sufridas_txt(self, options):
        return {
            "file_name": "Retenciones IVA Sufridas.txt",
            "file_content": self._vat_perc_ret_get_txt_files(options, "ret"),
            "file_type": "txt",
        }

    def perc_iva_sufridas_txt(self, options):
        return {
            "file_name": "Percepciones IVA Sufridas.txt",
            "file_content": self._vat_perc_ret_get_txt_files(options, "perc"),
            "file_type": "txt",
        }

    def _vat_perc_ret_get_txt_files(self, options, file_type):
        """Returns VAT txt content"""
        move_lines = self._vat_ret_perc_get_txt_lines(options, file_type)
        return "".join(self._get_vat_txt_content(move_lines, file_type)).encode("ISO-8859-1", "ignore")

    def _vat_ret_perc_get_txt_lines(self, options, file_type):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id", "=", False),
        ] + get_standard_lines_domain(self.env.company.ids, options)

        if file_type == "ret":
            # TODO: ver que agregamos en el domain para retenciones iva sufridas
            # las identificamos por tax group?
            domain += [("tax_line_id.l10n_ar_withholding_payment_type", "=", "customer")]
        elif file_type == "perc":
            domain += [
                ("tax_line_id.type_tax_use", "=", "purchase"),
                ("tax_line_id.tax_group_id.l10n_ar_tribute_afip_code", "=", "06"),
            ]

        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _get_vat_txt_content(self, move_lines, file_type):
        """Returns the lines to be printed in the txt file.
        Implementado segun especificación indicada en ticket 54274.
        """
        lines = []
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""
            if file_type == "ret":
                payment = line.payment_id
                # regimen (long 3)
                line_withholding_tax = line.withholding_id._get_withholding_tax()
                codigo_regimen = line_withholding_tax.l10n_ar_code
                if not codigo_regimen:
                    raise RedirectWarning(
                        message=_(
                            'No hay código de régimen en la configuración del impuesto "%(tax_name)s"',
                            tax_name=line_withholding_tax.name,
                        ),
                        action=line_withholding_tax.get_formview_action(),
                        button_text=_("Edit tax"),
                    )
                if len(codigo_regimen) < 3:
                    raise RedirectWarning(
                        message=_(
                            'El código de régimen tiene que tener 3 dígitos en la configuración del impuesto "%(tax_name)s"',
                            tax_name=line_withholding_tax.name,
                        ),
                        action=line_withholding_tax.get_formview_action(),
                        button_text=_("Edit tax"),
                    )
                content += codigo_regimen[:3]

                # cuit agente (long 11)
                content += payment.partner_id.ensure_vat()

                # fecha retención (long 10)
                content += fields.Date.from_string(payment.date).strftime("%d/%m/%Y")

                # número comprobante (long 16)
                content += re.sub(r"[^0-9\.]", "", line.withholding_id.name).ljust(16, "0")

                # Aclaración importante: estamos agregando ceros entre el número de comprobante y el importe de retención
                # esto contradice la especificación que dice que debe haber espacios pero en la tarea 31418 nos indicaron
                # que debe haber espacios. Ver nota en dicha tarea 14/07/2023 10:31:00 y 13/07/2023 14:39:47
                # importe retención (long 16)
                content += "%016.2f" % line.balance
                content += "\r\n"
            elif file_type == "perc":
                tax = line._get_settlement_tax()
                # regimen (long 3)
                codigo_regimen = tax.l10n_ar_code
                if not codigo_regimen:
                    raise RedirectWarning(
                        message=_(
                            'No hay código de régimen en la configuración del impuesto "%(tax_name)s"',
                            tax_name=tax.name,
                        ),
                        action=tax.get_formview_action(),
                        button_text=_("Edit tax"),
                    )
                if len(codigo_regimen) < 3:
                    raise RedirectWarning(
                        message=_(
                            'El código de régimen tiene que tener 3 dígitos en la configuración del impuesto "%(tax_name)s"',
                            tax_name=tax.name,
                        ),
                        action=tax.get_formview_action(),
                        button_text=_("Edit tax"),
                    )
                content += codigo_regimen[:3]

                # cuit agente (long 11)
                content += line.move_id.partner_id.ensure_vat()

                # fecha retención (long 10)
                content += fields.Date.from_string(line.move_id.invoice_date).strftime("%d/%m/%Y")

                # número comprobante (long 16)
                content += line.move_id.l10n_latam_document_number.ljust(16)

                # importe retención (long 16)
                content += "%16.2f" % line.balance
                content += "\r\n"
            lines.append(content)
        return lines
