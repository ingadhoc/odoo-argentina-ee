# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .helpers import get_standard_lines_domain, remove_accents_and_dieresis


class L10n_ArTucumanReportHandler(models.AbstractModel):
    _name = "l10n_ar.tucuman.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian Tucumán Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Datos",
                "sequence": 30,
                "action": "export_file",
                "action_param": "tucuman_datos_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT RETPER",
                "sequence": 30,
                "action": "export_file",
                "action_param": "tucuman_retper_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT NCFACT",
                "sequence": 30,
                "action": "export_file",
                "action_param": "tucuman_ncfact_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
        ]
        options["buttons"].extend(txt_export_button)

    def tucuman_datos_txt(self, options):
        return {
            "file_name": "DATOS.txt",
            "file_content": self._tucuman_get_txt_files(options, file_type="datos"),
            "file_type": "txt",
        }

    def tucuman_retper_txt(self, options):
        return {
            "file_name": "RETPER.TXT",
            "file_content": self._tucuman_get_txt_files(options, file_type="retper"),
            "file_type": "txt",
        }

    def tucuman_ncfact_txt(self, options):
        return {
            "file_name": "NCFACT.TXT",
            "file_content": self._tucuman_get_txt_files(options, file_type="ncfact"),
            "file_type": "txt",
        }

    def _tucuman_get_txt_files(self, options, file_type):
        """Returns Tucumán txt content"""
        move_lines = self._tucuman_get_txt_lines(options, file_type)
        self._iibb_tucuman_validations(move_lines)
        if file_type == "datos":
            return "".join(self._get_tucuman_datos_txt_file(move_lines)).encode("ISO-8859-1", "ignore")
        if file_type == "retper":
            return "".join(self._get_tucuman_retper_txt_file(move_lines)).encode("ISO-8859-1", "ignore")
        if file_type == "ncfact":
            return "".join(self._get_tucuman_ncfact_txt_file(move_lines)).encode("ISO-8859-1", "ignore")

    def _tucuman_get_txt_lines(self, options, file_type):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "=", "T"),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
            "|",
            ("tax_line_id.type_tax_use", "=", "sale"),
            ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
        ] + get_standard_lines_domain(self.env.company.ids, options)

        # lo hacemos igual que está hoy, probablemente tengamos que hacer busqueda negativa para los otros casos?
        if file_type == "ncfact":
            domain += [("move_id.move_type", "=", "out_refund")]

        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    @api.model
    def _iibb_tucuman_validations(self, move_lines):
        """Validaciones para el archivo TXT Retenciones/Percepciones Tucuman. Si no hay errores este método no
        devuelve nada, de lo contrario se lanzará mensaje de error que corresponda indicando lo que el usuario debe
        corregir para poder generar el archivo."""
        if nc_without_reversed_entry_id := move_lines.filtered(
            lambda x: x.move_type == "out_refund" and not x.move_id.reversed_entry_id
        ):
            raise UserError(
                _(
                    "Algunos comprobantes rectificativos no contienen información de que "
                    "comprobante original están revirtiendo:\n %s"
                )
                % (", ".join(nc_without_reversed_entry_id.mapped("move_id.name")))
            )
        if moves_without_street_city_state := move_lines.filtered(
            lambda x: not x.partner_id.street
            or not x.partner_id.city
            or not x.partner_id.state_id
            or not x.partner_id.zip
        ):
            raise UserError(
                _(
                    "Algunos comprobantes no contienen información acerca de la calle/ciudad/provincia/cod "
                    "postal del contacto:\n %s"
                )
                % (", ".join(moves_without_street_city_state.mapped("move_id.name")))
            )
        move_lines_with_five_digits_pos = move_lines.filtered(
            lambda x: x.move_id._l10n_ar_get_document_number_parts(
                x.move_id.l10n_latam_document_number, x.l10n_latam_document_type_id.code
            )["point_of_sale"]
            > 9999  # Verificar si el punto de venta es mayor a 9999
        )
        if move_lines_with_five_digits_pos:
            raise UserError(
                _(
                    "Algunos comprobantes tienen punto de venta de 5 dígitos y deben tener de 4 dígitos para "
                    "poder generar el archivo txt de retenciones y percepciones de Tucuman:\n %s"
                )
                % (", ".join(move_lines_with_five_digits_pos.mapped("move_id.name")))
            )

    def _get_tucuman_datos_txt_file(self, move_lines):
        """Genera el contenido del archivo DATOS.txt para Tucumán."""
        lines = []
        for line in move_lines:
            content = ""
            is_perception = line.move_id.is_invoice()
            # 1, FECHA, longitud: 8. Formato AAAAMMDD
            content += fields.Date.from_string(line.date).strftime("%Y%m%d")
            # 2, TIPODOC, longitud: 2
            content += line.partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code
            # 3, DOCUMENTO, longitud: 11
            content += line.partner_id.l10n_ar_vat
            # 4, TIPO COMP, longitud: 2
            # 99 para retenciones por el ejemplo que pasó en el archivo adjunto el cliente en la tarea 38200
            content += line.move_id.l10n_latam_document_type_id.code.zfill(2) if is_perception else "99"
            # 5, LETRA, longitud: 1
            content += line.move_id.l10n_latam_document_type_id.l10n_ar_letter if is_perception else " "
            # 6, COD. LUGAR EMISION, longitud: 4
            document_number_parts = line.move_id._l10n_ar_get_document_number_parts(
                line.move_id.l10n_latam_document_number, line.l10n_latam_document_type_id.code
            )
            content += str(document_number_parts["point_of_sale"]).zfill(4)
            # 7, NUMERO, longitud: 8
            content += str(document_number_parts["invoice_number"]).zfill(8)
            # 8, BASE_CALCULO, longitud: 15,2
            # TODO: le tuve que agregar abs(), investigar si está bien que en facturas
            # de cliente line.tax_base_amount da negativo y por qué da positivo en nc
            # En 18 no hace falta agregarle abs()
            content += "%015.2f" % (abs(line.tax_base_amount) if is_perception else line.withholding_id.base_amount)
            # 9, PORCENTAJE/ALICUOTA, longitud: 6,3
            tax = line._get_settlement_tax()
            content += "%06.3f" % tax.amount
            # 10, MONTO_RET/PER, longitud: 15,2
            content += "%015.2f" % abs(line.balance)
            content += "\r\n"
            lines.append(content)
        return lines

    def _get_tucuman_retper_txt_file(self, move_lines):
        """Genera el contenido del archivo RETPER.txt para Tucumán."""
        lines = []
        for line in move_lines:
            content = ""
            is_perception = line.move_id.is_invoice()
            # 1, FECHA, longitud: 8. Formato AAAAMMDD
            content += fields.Date.from_string(line.date).strftime("%Y%m%d")
            # 2, TIPODOC, longitud: 2
            content += line.partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code
            # 3, DOCUMENTO, longitud: 11
            content += line.partner_id.l10n_ar_vat
            # 4, TIPO COMP, longitud: 2
            # 99 para retenciones por el ejemplo que pasó en el archivo adjunto el cliente en la tarea 38200
            content += line.move_id.l10n_latam_document_type_id.code.zfill(2) if is_perception else "99"
            # 5, LETRA, longitud: 1
            content += line.move_id.l10n_latam_document_type_id.l10n_ar_letter if is_perception else " "
            # 6, COD. LUGAR EMISION, longitud: 4
            document_number_parts = line.move_id._l10n_ar_get_document_number_parts(
                line.move_id.l10n_latam_document_number, line.l10n_latam_document_type_id.code
            )
            content += str(document_number_parts["point_of_sale"]).zfill(4)
            # 7, NUMERO, longitud: 8
            content += str(document_number_parts["invoice_number"]).zfill(8)
            # 8, BASE_CALCULO, longitud: 15,2
            # 8, BASE_CALCULO, longitud: 15,2
            # TODO: le tuve que agregar abs(), investigar si está bien que en facturas
            # de cliente line.tax_base_amount da negativo y por qué da positivo en nc
            # En 18 no hace falta agregarle abs()
            content += "%015.2f" % (abs(line.tax_base_amount) if is_perception else line.withholding_id.base_amount)
            # 9, PORCENTAJE/ALICUOTA, longitud: 6,3
            tax = line._get_settlement_tax()
            content += "%06.3f" % tax.amount
            # 10, MONTO_RET/PER, longitud: 15,2
            content += "%015.2f" % abs(line.balance)
            content += "\r\n"
            lines.append(remove_accents_and_dieresis(content))
        return lines

    def _get_tucuman_ncfact_txt_file(self, move_lines):
        """Genera el contenido del archivo NCFACT.txt para Tucumán."""
        lines = []
        for line in move_lines:
            content = ""
            nc_document_number_parts = line.move_id._l10n_ar_get_document_number_parts(
                line.move_id.l10n_latam_document_number, line.l10n_latam_document_type_id.code
            )
            # 1, COD. LUGAR EMISION NC, longitud: 4
            content += str(nc_document_number_parts["point_of_sale"]).zfill(4)
            # 2, NUMERO NV, longitud: 8
            content += str(nc_document_number_parts["invoice_number"]).zfill(8)
            # 3, COD LUGAR EMISION FAC, longitud: 4
            document_number_parts = line.move_id._l10n_ar_get_document_number_parts(
                line.move_id.reversed_entry_id.l10n_latam_document_number,
                line.move_id.reversed_entry_id.l10n_latam_document_type_id.code,
            )
            content += str(document_number_parts["point_of_sale"]).zfill(4)
            # 4, NUMERO FAC, longitud: 8
            content += str(document_number_parts["invoice_number"]).zfill(8)
            # 5, TIPO FAC, longitud: 2
            content += line.move_id.reversed_entry_id.l10n_latam_document_type_id.code.zfill(2)
            content += "\r\n"
            lines.append(content)
        return lines
