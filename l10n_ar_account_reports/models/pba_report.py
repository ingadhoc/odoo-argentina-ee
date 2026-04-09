# Part of Odoo. See LICENSE file for full copyright and licensing details.
# TODO mejorar esa importación ya que no sabemos si estos helpers van a seguir en
# l10n_ar_account_tax_settlement
import logging
import re

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

from .helpers import format_amount, get_line_tax_base, get_standard_lines_domain

_logger = logging.getLogger(__name__)


class L10n_ArPbaReportHandler(models.AbstractModel):
    _name = "l10n_ar.pba.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian PBA Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones IIBB aplicadas ARBA desde 01/03/2026: Retenciones (excepto actividad 29, 7 quincenal, 7 y 17 de Bancos)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_ret_desde_01032026_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT Retenciones IIBB aplicadas ARBA alta por lote A-122R desde 01/03/2026.",
                "sequence": 30,
                "action": "export_file",
                "action_param": "pba_alta_ret_lote_a122r_01032026_txt",
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

    def pba_ret_desde_01032026_txt(self, options):
        move_lines = self._pba_get_txt_lines(options, "ret")
        period = move_lines and fields.Date.to_date(move_lines[0].date).strftime("%Y%mX") or ""
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "6",  # 6 serian las retenciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files_desde_01032026(options, "ret", move_lines),
            "file_type": "txt",
        }

    def pba_alta_ret_lote_a122r_01032026_txt(self, options):
        move_lines = self._pba_get_txt_lines(options, "ret_a122r")
        period = move_lines and fields.Date.to_date(move_lines[0].date).strftime("%Y%mX") or ""
        # ER-vat-PERIODO-ACTIVIDAD-LOTE_MD5
        # Esto funciona para el tipo de actividad 6 que es el regimen de retenciones generales.
        # En el futuro si agregamos mas regimenes/actividades debemos de sacar este dato
        # de la configuracion de la compañía
        file_name = "ER-%s-%s-%s-LOTEXXXXX.txt" % (
            self.env.company.vat,
            period,
            "6",  # 6 serian las retenciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files_desde_01032026(options, "ret_a122r", move_lines),
            "file_type": "txt",
        }

    def pba_perc_desde_01032026_txt(self, options):
        move_lines = self._pba_get_txt_lines(options, "perc")
        period = move_lines and fields.Date.to_date(move_lines[0].date).strftime("%Y%mX") or ""
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "7",  # 7 serian las percepciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files_desde_01032026(options, "perc", move_lines),
            "file_type": "txt",
        }

    def pba_perc_act_7_desde_01032026_txt(self, options):
        move_lines = self._pba_get_txt_lines(options, "perc_act_7")
        period = move_lines and fields.Date.to_date(move_lines[0].date).strftime("%Y%mX") or ""
        file_name = "AR-%s-%s-%s-LOTEX.txt" % (
            self.env.company.vat,
            period,
            "7",  # 7 serian las percepciones
        )
        return {
            "file_name": file_name,
            "file_content": self._pba_get_txt_files_desde_01032026(options, "perc_act_7", move_lines),
            "file_type": "txt",
        }

    def _pba_get_txt_files_desde_01032026(self, options, file_type, move_lines):
        """Returns PBA txt content"""
        if file_type == "ret_a122r":
            return "".join(self._get_pba_alta_ret_lote_a122r_txt_content_desde_01032026(move_lines)).encode(
                "ISO-8859-1", "ignore"
            )
        else:
            return "".join(self._get_pba_txt_content_desde_01032026(move_lines, file_type)).encode(
                "ISO-8859-1", "ignore"
            )

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

        if file_type in ["ret", "ret_a122r"]:
            domain += [("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier")]
        elif file_type in ["perc", "perc_act_7"]:
            domain += [("tax_line_id.type_tax_use", "=", "sale")]
        move_lines = self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")
        if file_type == "ret_a122r" and self.env["ir.module.module"].search(
            [("name", "=", "l10n_ar_arba_ws"), ("state", "in", ["installed", "to upgrade"])]
        ):
            move_lines = move_lines.filtered(lambda line: not line.withholding_id.l10n_ar_cert_number)
        return move_lines

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
        percepciones_monto_modificado = []
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
            monto_imponible = float_round(-get_line_tax_base(line), precision_digits=2)
            content += format_amount(monto_imponible, 14, 2, ",")
            # Alícuota (long 5.2, desde 53 a 57)
            alicuota = float_round(tax.amount, precision_digits=2)
            content += "%05.2f" % alicuota
            # este es para el primer tipo de la especificación
            # Importe de la percepción (long 13.2, desde 58 hasta 70)
            # Con separador decimal (, o .). Mayor a cero, excepto para notas de crédito donde
            # debe ser negativo. Completar con ceros a la izquierda. En las notas de crédito el
            # signo negativo ocupará la primera posición a la izquierda. Formato: 9999999999.99
            importe_percepcion = format_amount(-line.balance, 13, 2, ",")
            importe_percepcion_calculado = False
            # por ahora solo hacemos este cálculo para percepciones,
            # TODO ver cuando podemos hacer revert de esto en tarea 66283
            if file_type in ["perc", "perc_act_7"]:
                importe_percepcion_calculado = format_amount(monto_imponible * alicuota / 100, 13, 2, ",")
            # ARBA valida importe = base * alícuota; informar el importe calculado
            # cuando difiere del original por redondeos (calculado por odoo).
            if importe_percepcion_calculado and importe_percepcion != importe_percepcion_calculado:
                percepciones_monto_modificado.append(
                    {
                        "id": line.id,
                        "nombre": line.move_id.display_name,
                        "importe_original": importe_percepcion,
                        "importe_calculado": importe_percepcion_calculado,
                    }
                )
                content += importe_percepcion_calculado
            else:
                content += importe_percepcion
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
        if percepciones_monto_modificado:
            comprobantes_modificados = "\n".join(
                "%(id)s - %(nombre)s - %(importe_original)s - %(importe_calculado)s" % percepcion
                for percepcion in percepciones_monto_modificado
            )
            _logger.info(
                "Percepciones ARBA con importe ajustado:\nid - nombre - importe original - importe calculado\n%s",
                comprobantes_modificados,
            )
        return lines

    def _get_pba_alta_ret_lote_a122r_txt_content_desde_01032026(self, move_lines):
        """Desarrollado según especificación Webservice (A122R):
        https://web.arba.gov.ar/Instructivos-y-Marco-Normativo-A-122R
        (ese enlace se obtiene de https://web.arba.gov.ar/agentes#presentacion-de-ddjj ,
        luego hay que ir a la sección "Comprobantes de Retención (A-122R) Nuevo" y
        hacer click en "Instructivo y Marco Normativo"). Finalmente descargar la especificación
        donde dice 'Descargar PDF'. En este método se desarrolla el punto 1
        'Retenciones (Régimen General y Regímenes Especiales)'
        Solo para retenciones. Vigente desde 01/03/2026."""
        lines = []
        for line in move_lines:
            content = ""
            # Nro. transacción Agente (numérico 20, desde 1 hasta 20. Formato 99999999999999999999)
            content += re.sub(r"[^0-9]", "", str(line.name))[-20:].zfill(20)

            # CUIT contribuyente Retenido (long 11, desde 21 hasta 31. Formato 99999999999)
            content += line.partner_id.ensure_vat()

            move = line.move_id
            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number, move.l10n_latam_document_type_id.code
            )
            pto_venta = "{:0>5d}".format(document_parts["point_of_sale"])[-5:]

            # Sucursal (long 5, desde 32 hasta 36)
            # Mayor a cero. Completar con ceros a la izquierda.
            content += str(pto_venta)

            # Fecha de Operación (long 10, desde 37 hasta 46. Formato dd/mm/aaaa)
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # Alícuota (long 5.2, desde 47 a 51)
            tax = line._get_settlement_tax()
            content += "%05.2f" % tax.amount

            # Base imponible (long 16.2, desde 52 hasta 67)
            # Con separador decimal (, o .). Mayor a cero, o Excepto para Nota de crédito,
            # donde el importe debe ser negativo y la base debe ser menor o igual a cero.
            # Completar con ceros a la izquierda. En las notas de crédito el signo negativo
            # ocupará la primera posición a la izquierda. Formato: 99999999999.99
            content += "%016.2f" % line.withholding_id.base_amount

            content += "\r\n"

            lines.append(content)
        return lines
