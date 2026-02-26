# Part of Odoo. See LICENSE file for full copyright and licensing details.
# TODO mejorar esa importación ya que no sabemos si estos helpers van a seguir en
# l10n_ar_account_tax_settlement
from odoo import _, fields, models
from odoo.exceptions import UserError

from .helpers import format_amount, get_line_tax_base, get_standard_lines_domain


class L10n_ArPbaReportHandler(models.AbstractModel):
    _name = "l10n_ar.pba.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian PBA Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones (excepto actividad 29, 7 quincenal, 7 y 17 de Bancos)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_ret_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT Percepciones (excepto actividad 29, 7 quincenal, 7 y 17 de Bancos)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_perc_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT Percepciones Act. 7 método Percibido (quincenal)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_perc_act_7_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT Retenciones IIBB aplicadas ARBA desde 01/03/2026: Retenciones (excepto actividad 29, 7 quincenal, 7 y 17 de Bancos)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_ret_desde_01032026_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT Percepciones IIBB aplicadas ARBA desde 01/03/2026: Percepciones (excepto actividad 29, 7 quincenal, 7 y 17 de Bancos)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_perc_desde_01032026_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT Percepciones IIBB aplicadas ARBA desde 01/03/2026: Percepciones Act. 7 método Percibido (quincenal)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_perc_act_7_desde_01032026_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
        ]
        options["buttons"].extend(txt_export_button)

    def pba_ret_txt(self, options):
        period = 1
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "6",  # 6 serian las retenciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files(options, "ret"),
            "file_type": "txt",
        }

    def pba_perc_txt(self, options):
        period = 1
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "7",  # 7 serian las percepciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files(options, "perc"),
            "file_type": "txt",
        }

    def pba_perc_act_7_txt(self, options):
        period = 1
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "7",  # 7 serian las percepciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files(options, "perc_act_7"),
            "file_type": "txt",
        }

    def pba_ret_desde_01032026_txt(self, options):
        period = 1
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "6",  # 7 serian las percepciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files_desde_01032026(options, "ret"),
            "file_type": "txt",
        }

    def pba_perc_desde_01032026_txt(self, options):
        period = 1
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "7",  # 7 serian las percepciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files_desde_01032026(options, "perc"),
            "file_type": "txt",
        }

    def pba_perc_act_7_desde_01032026_txt(self, options):
        period = 1
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "7",  # 7 serian las percepciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files_desde_01032026(options, "perc_act_7"),
            "file_type": "txt",
        }

    def _pba_get_txt_files_desde_01032026(self, options, file_type):
        """Returns PBA txt content"""
        move_lines = self._pba_get_txt_lines(options, file_type)
        return "".join(self._get_pba_txt_content_desde_01032026(move_lines, file_type)).encode("ISO-8859-1", "ignore")

    def _pba_get_txt_files(self, options, file_type):
        """Returns PBA txt content"""
        move_lines = self._pba_get_txt_lines(options, file_type)
        return "".join(self._get_pba_txt_content(move_lines, file_type)).encode("ISO-8859-1", "ignore")

    def _pba_get_txt_lines(self, options, file_type):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "=", "B"),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
        ] + get_standard_lines_domain(self.env.company.ids, options)

        if file_type == "ret":
            domain += [("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier")]
        elif file_type in ["perc", "perc_act_7"]:
            domain += [("tax_line_id.type_tax_use", "=", "sale")]
        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _get_pba_txt_content(self, move_lines, file_type):
        """Returns the lines to be printed in the txt file.
        Por ahora es el de arba, renombrar o generalizar para otros
        Implementado segun esta especificacion
        https://drive.google.com/file/d/0B3trzV0e2WzveHhBTk9xWEl6RjA/view
        o descargarlo desde https://web.arba.gov.ar/agentes#presentacion-de-ddjj
        hacer click en "Instructivos y Marco Normativo - NOVEDAD -" dentro de
        DDJJ Periódicas Web IIBB
        Implementados:
            - 1.2 Percepciones Act. 7 método Percibido (quincenal)
            - 1.7 Retenciones ( excepto actividad 26, 6 de Bancos y 17 de
            Bancos y No Bancos)"""
        lines = []
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""
            move = line.move_id
            line.partner_id.ensure_vat()

            # CUIT contribuyente percibido (long 13, desde 1 hasta 13, formato 99-99999999-9))
            content = line.partner_id.l10n_ar_formatted_vat
            # Fecha percepción/retención (long 10, desde 14 hasta 23, formato dd/mm/aaaa)
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")
            # solo para percepciones
            if file_type in ["perc", "perc_act_7"]:
                internal_type = line.l10n_latam_document_type_id.internal_type
                document_code = line.l10n_latam_document_type_id.code
                # Tipo de comprobante (long 1, desde 24 hasta 24)
                content += (
                    document_code in ["201", "206", "211"]
                    and "E"
                    or document_code in ["203", "208", "213"]
                    and "H"
                    or document_code in ["202", "207", "212"]
                    and "I"
                    or internal_type == "invoice"
                    and "F"
                    or internal_type == "credit_note"
                    and "C"
                    or internal_type == "debit_note"
                    and "D"
                    or "R"
                )
                # Letra del comprobante (long 1, desde 25 hasta 25)
                content += line.l10n_latam_document_type_id.l10n_ar_letter

            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number, move.l10n_latam_document_type_id.code
            )
            # si el punto de venta es de 5 digitos no encontramos doc
            # que diga como proceder, tomamos los ultimos 4 digitos
            pto_venta = "{:0>4d}".format(document_parts["point_of_sale"])[-4:]
            nro_documento = "{:0>8d}".format(document_parts["invoice_number"])[-8:]
            # Número sucursal (long 4)
            content += str(pto_venta)
            # Número emisión (long 8)
            content += str(nro_documento)

            # solo para percepciones
            if file_type in ["perc", "perc_act_7"]:
                # Monto imponible (long 12)
                content += format_amount(-get_line_tax_base(line), 12, 2, ",")

            # este es para el primer tipo de la especificación (importe de percepción/retención)
            content += format_amount(-line.balance, 11, 2, ",")

            # solo para percepciones
            # según especificación se requiere fecha nuevamente
            # por ahora lo sacamos ya que en ticket 16448 nos mandaron ej.
            # donde no se incluía, en realidad tal vez depende de la actividad
            # ya que en la primer tabla del pdf la agrega y en la segunda no
            if file_type == "perc_act_7":
                content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")
            # Tipo Operación (long 1, "A" significa "Alta")
            content += "A"
            content += "\r\n"

            lines.append(content)
        return lines

    def _get_pba_txt_content_desde_01032026(self, move_lines, file_type):
        """Returns the lines to be printed in the txt file."""
        lines = []
        # TODO implementar
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""

            # pay_group = payment.payment_group_id
            move = line.move_id
            internal_type = line.l10n_latam_document_type_id.internal_type
            document_code = line.l10n_latam_document_type_id.code

            line.partner_id.ensure_vat()

            # CUIT contribuyente Percibido (long 13, desde 1 hasta 13. Formato 99-99999999-9)
            content = line.partner_id.l10n_ar_formatted_vat
            # Fecha Percepción (long 10, desde 14 hasta 23. Formato dd/mm/aaaa)
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # solo para percepciones
            if file_type in ["perc", "perc_act_7"]:
                # Tipo de Comprobante (long 1, desde 24 hasta 24)
                # Valores F=Factura, R=Recibo, C=Nota Crédito, D =Nota Debito, V=Nota de Venta, E=Factura de Crédito
                # Electrónica, H=Nota de Crédito Electrónica, I=Nota de Débito Electrónica.
                content += (
                    document_code in ["201", "206", "211"]
                    and "E"
                    or document_code in ["203", "208", "213"]
                    and "H"
                    or document_code in ["202", "207", "212"]
                    and "I"
                    or internal_type == "invoice"
                    and "F"
                    or internal_type == "credit_note"
                    and "C"
                    or internal_type == "debit_note"
                    and "D"
                    or "R"
                )
                # Letra Comprobante (long 1, desde 25 hasta 25. Valores A,B,C, o “ ” (blanco)).
                content += line.l10n_latam_document_type_id.l10n_ar_letter
            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number, move.l10n_latam_document_type_id.code
            )
            pto_venta = "{:0>5d}".format(document_parts["point_of_sale"])[-5:]
            nro_documento = "{:0>8d}".format(document_parts["invoice_number"])[-8:]
            # Numero Sucursal (long 5, desde 26 hasta 30)
            # Mayor a cero. Completar con ceros a la izquierda.
            content += str(pto_venta)
            # Numero Emisión (long 8, desde 31 a 38).
            # Mayor a cero. Completar con ceros a la izquierda
            content += str(nro_documento)

            tax = line._get_settlement_tax()
            # Monto imponible (long 14.2, desde 39 hasta 52)
            # Con separador decimal (, o .). Mayor a cero, o Excepto para Nota de crédito,
            # donde el importe debe ser negativo y la base debe ser menor o igual a cero.
            # Completar con ceros a la izquierda. En las notas de crédito el signo negativo
            # ocupará la primera posición a la izquierda. Formato: 99999999999.99
            content += format_amount(-get_line_tax_base(line), 14, 2, ",")
            # Alícuota (long 5.2, desde 53 a 57)
            content += "%05.2f" % tax.amount
            # este es para el primer tipo de la especificación
            # Importe de la percepción (long 13.2, desde 58 hasta 70)
            # Con separador decimal (, o .). Mayor a cero, excepto para notas de crédito donde
            # debe ser negativo. Completar con ceros a la izquierda. En las notas de crédito el
            # signo negativo ocupará la primera posición a la izquierda. Formato: 9999999999.99
            content += format_amount(-line.balance, 13, 2, ",")

            # según especificación se requiere fecha nuevamente
            # por ahora lo sacamos ya que en ticket 16448 nos mandaron ej.
            # donde no se incluía, en realidad tal vez depende de la actividad
            # ya que en la primer tabla del pdf la agrega y en la segunda no
            if file_type == "perc_act_7":
                # Fecha Emisión (long 10, desde 71 hasta 80)
                content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")
            # Tipo Operación (long 1, desde 71 hasta 71 o desde 81 a 81 si es act_7)
            # A= Alta, B=Baja, M=Modificación.
            content += "A"
            content += "\r\n"

            lines.append(content)
        return lines
