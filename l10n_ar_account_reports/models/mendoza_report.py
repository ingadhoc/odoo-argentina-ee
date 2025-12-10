# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError

from .helpers import get_standard_lines_domain


class L10n_ArMendozaReportHandler(models.AbstractModel):
    _name = "l10n_ar.mendoza.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian Mendoza Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "mendoza_ret_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
        ]

        options["buttons"].extend(txt_export_button)

    def mendoza_ret_txt(self, options):
        tipo_agente = "rr"  # This value is fixed just because we are doing the retention txt, when adding the
        # perception we need to change it
        cuit = self.env.company.vat
        date_from = options["date"]["date_from"]
        periodo = fields.Date.from_string(date_from).strftime("%Y") or ""  # 'pppp' AÑO '2020'
        cuota = fields.Date.from_string(date_from).strftime("%m") or ""  # 'cc'

        filename = "%s%s%s%s.txt" % (tipo_agente, cuit, periodo, cuota)

        return {
            "file_name": filename,
            "file_content": self._mendoza_get_txt_files(options),
            "file_type": "txt",
        }

    def _mendoza_get_txt_files(self, options):
        """Returns Mendoza txt content"""
        move_lines = self._mendoza_get_txt_lines(options)
        return "".join(self._get_mendoza_txt_content(move_lines)).encode("ISO-8859-1", "ignore")

    def _mendoza_get_txt_lines(self, options):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "=", "M"),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
            ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
        ] + get_standard_lines_domain(self.env.company.ids, options)
        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _get_mendoza_txt_content(self, move_lines):
        """Returns the lines to be printed in the txt file."""
        lines = []
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""
            partner = line.partner_id
            payment = line.payment_id
            move = line.move_id

            tax = line._get_settlement_tax()
            if not payment:
                continue

            # Campo 1: CUIT char(13). CUIT del Sujeto retenido o percibido. Ejemplo: 20-10111222-3
            # Example "30-58710878-6"
            partner.ensure_vat()
            content = partner.l10n_ar_formatted_vat
            # Campo 2: Denominación char(80). Apellido y Nombre o Razón Social. Formato: 80 posiciones, se completa con
            # blancos a la derecha.
            # Example "ELECTRICIDAD MAZA SRL                                                           "
            content += f"{partner.name:80.80}"

            # Campo 3: Fecha Comprobante char(8). Fecha del Comprobante de Retención/Percepción según Res.40/2012 (ddmmaaaa)
            # Example s"16052020"
            content += fields.Date.from_string(move.date).strftime("%d%m%Y")

            # Campo 4: Comprobante char(12)- Número de Comprobante de Retención/Percepción según Res.40/2012.
            # Formato: 999999999999 (rellenar con ceros (0) a la izquierda) Ejemplo: 000000001521
            # Example "000000027860"
            if len(line.name) > 12:
                prefix, rest = line.name.split("-", 1)
                exceso = len(line.name) - 12
                rest = rest[exceso:]  # quitamos solo los ceros necesarios
                name = prefix + "-" + rest
            content += (name or "").rjust(12, "0")[:12]  # we are forcing 12 first numbers always.

            # Campo 5: Fecha Ret./Perc. char(8)- Fecha de efectuada la retención / percepción (ddmmaaaa)
            # Example "16052020"
            content += fields.Date.from_string(payment.date).strftime("%d%m%Y")

            # Campo 6. Base Imponible char(15). Formato: 999999999999.99 (doce enteros, punto decimal y dos decimales,
            # dejando espacios en blanco a izquierda para completar las 15 posiciones). Ejemplo: "         345.21"
            # Example "000000027229.33"
            content += "%15.2f" % line.withholding_id.base_amount

            # Campo 7: Alícuota char(5). Alícuota para la retención y/o percepción. Formato: 99.99 (dos enteros,
            # punto decimal y dos decimales. Ejemplo: " 3.00"
            # Example "03.00"
            content += "%5.2f" % tax.amount

            # Campo 8: Importe Ret./Perc. char(15). Importe retenido y/o percibido. Formato: 999999999999.99 (doce enteros,
            # punto decimal y dos decimales, dejando espacios en blanco a izquierda para completar las 15 posiciones).
            # Ejemplo: "          34.50" "000000000816.88"
            content += "%15.2f" % -line.balance

            content += "\r\n"

            lines.append(content)
        return lines
