# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import _, fields, models
from odoo.exceptions import UserError

from .helpers import get_standard_lines_domain


class L10n_ArSicoreReportHandler(models.AbstractModel):
    _name = "l10n_ar.sicore.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian SICORE Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # TODO falta implementar percepciones aplicadas de iva
        # Add export button
        txt_export_button = {
            "name": _("Sicore Profits Withholdings TXT"),
            "sequence": 30,
            "action": "export_file",
            "action_param": "sicore_book_export_files_to_txt",
            "file_export_type": "TXT",
            "branch_allowed": True,
        }

        options["buttons"].append(txt_export_button)

    def sicore_book_export_files_to_txt(self, options):
        """Export method that lets us export the SICORE book to a txt file.
        It contains the file that we upload to SICORE application."""
        return {
            "file_name": _("SICORE_profits_withholdings.txt"),
            "file_content": self._sicore_book_get_txt_files(options),
            "file_type": "txt",
        }

    def _sicore_book_get_txt_files(self, options):
        """Returns SICORE txt content"""
        move_lines = self._sicore_book_get_txt_lines(options)
        return "".join(self._get_sicore_txt_content(move_lines)).encode("ISO-8859-1", "ignore")

    def _sicore_book_get_txt_lines(self, options):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_tax_type", "in", ["earnings", "earnings_scale"]),
            ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ("tax_line_id.country_code", "=", "AR"),
        ] + get_standard_lines_domain(self.env.company.ids, options)
        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _get_sicore_txt_content(self, move_lines):
        """Returns the lines to be printed in the txt file."""
        lines = []
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""

            partner = line.partner_id
            if not partner.l10n_latam_identification_type_id.l10n_ar_afip_code:
                raise UserError(
                    _(
                        'The identification type "%(identification_type)s" does not have ARCA code set.',
                        identification_type=partner.l10n_latam_identification_type_id.name,
                    )
                )
            if not partner.vat:
                raise UserError(
                    _(
                        'The partner "%(partner_name)s" (id %(partner_id)s) does not have the vat set.',
                        partner_name=partner.name,
                        partner_id=partner.id,
                    )
                )

            payment = line.payment_id
            move = line.move_id

            # Codigo del Comprobante (document code)        [ 2]
            content += (
                (payment.payment_type == "inbound" and "02") or (payment.payment_type == "outbound" and "06") or "00"
            )
            # Fecha Emision Comprobante (move line date)     [10] (dd/mm/yyyy)
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # Numero Comprobante (document number)           [16]
            content += f"{re.sub(r'[^0-9]', '', move.l10n_latam_document_number):0>16}"

            # Fecha de pago del comprobante (document amount)
            issue_date = payment.date

            # Importe Comprobante (document amount)           [16]
            content += f"{abs(payment.amount):016.2f}"
            # Codigo de Impuesto (tax code)            [ 4]
            # Codigo de Regimen (regime code)             [ 3]

            content += "0217"
            regimen = line.tax_line_id.l10n_ar_code

            content += f"{''.join(filter(str.isdigit, str(regimen))):0>3}" if regimen else "000"

            # Codigo de Operacion (operation code)           [ 1]
            content += "1"

            # Base de Calculo (base amount)               [14]
            content += f"{abs(line.tax_base_amount):014.2f}"

            # Fecha Emision Retencion (move line date)        [10] (dd/mm/yyyy)
            content += fields.Date.from_string(issue_date).strftime("%d/%m/%Y")

            # Codigo de Condicion (condition code)           [ 2]
            content += "01"

            # Retención Pract. a Suj. ..     [ 1]
            content += "0"

            # Importe de Retencion (withholding amount)          [14]
            content += f"{abs(line.balance):014.2f}"

            # Porcentaje de Exclusion (exclusion percentage)       [ 6]
            content += "000.00"

            # Fecha Emision Boletin          [10] (dd/mm/yyyy)
            content += fields.Date.from_string(issue_date).strftime("%d/%m/%Y")

            # Tipo Documento Retenido (document type code)       [ 2]
            content += f"{int(partner.l10n_latam_identification_type_id.l10n_ar_afip_code):02d}"

            # Numero Documento Retenido (vat)     [20]
            content += partner.vat.ljust(20)

            # Numero Certificado Original    [14]
            content += f"{0:014d}"

            content += "\r\n"

            lines.append(content)
        return lines
