# from odoo.tools.misc import formatLang
# from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import logging
import re
import unicodedata

from odoo import _, fields, models
from odoo.exceptions import RedirectWarning, ValidationError
from odoo.tools import ustr
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)

#########
# helpers
#########


def format_amount(amount, padding=15, decimals=2, sep=""):
    if amount < 0:
        template = "-{:0>%dd}" % (padding - 1 - len(sep))
    else:
        template = "{:0>%dd}" % (padding - len(sep))
    res = template.format(int(round(abs(amount) * 10**decimals, decimals)))
    if sep:
        res = f"{res[:-decimals]}{sep}{res[-decimals:]}"
    return res


def get_line_tax_base(move_line):
    return sum(move_line.move_id.line_ids.filtered(lambda x: move_line.tax_line_id in x.tax_ids).mapped("balance"))


def get_pos_and_number(full_number):
    """
    Para un numero nos fijamos si hay '-', si hay:
    * mas de 1, entonces devolvemos error
    * 1, entonces devolvemos las partes (solo parte númerica)
    * 0, entonces devolvemos '0' y parte númerica del número que se pasó
    """
    args = full_number.split("-")
    if len(args) == 1:
        # si no hay '-' tomamos punto de venta 0
        return ("0", re.sub("[^0-9]", "", args[0]))
    else:
        return re.sub("[^0-9]", "", args[0]), re.sub("[^0-9]", "", "".join(args[1:]))


def remove_accents_and_dieresis(input_str):
    """Suboptimal-but-better-than-nothing way to replace accented or dieresis-containing
    latin letters by an ASCII equivalent."""
    input_str = ustr(input_str)
    nkfd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nkfd_form if not unicodedata.combining(c)])


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # TODO ver como queremos separar la de santa fe, arba y demás. usamos uno
    # solo y luego logica adentro? un diario para cada una?
    settlement_tax = fields.Selection(
        selection_add=[
            # ('vat', 'VAT'),
            # ('profits', 'Profits'),
            ("misiones", "TXT IIBB aplicado DGR Misiones"),
            ("drei_aplicado", "TXT DREI Aplicado"),
            ("sicore_aplicado", "TXT SICORE Aplicado"),
            ("iibb_sufrido", "TXT IIBB p/ SIFERE"),
            ("iibb_aplicado_agip", "TXT Perc/Ret IIBB aplicadas AGIP"),
            ("iibb_aplicado_api", "TXT Perc/Ret IIBB aplicadas API"),
            ("iibb_aplicado_sircar", "TXT Perc/Ret IIBB aplicadas SIRCAR"),
            ("iibb_aplicado_dgr_mendoza", "TXT  Perc/Ret IIBB aplicado DGR Mendoza"),
            ("retenciones_iva", "TXT Retenciones/Percepciones Sufridas IVA"),
            (
                "iibb_aplicado_arba_desde_01032026",
                "TXT Perc/Ret IIBB aplicadas ARBA: Percepciones ( excepto actividad 29, 7 quincenal, 7 y 17 de Bancos) + TXT Ret IIBB aplicadas ARBA alta por lote A-122R. Vigente desde 01/03/2026",
            ),
            (
                "iibb_aplicado_arba_act_7_desde_01032026",
                "TXT Perc/Ret IIBB aplicadas ARBA: Percepciones Act. 7 método Percibido (quincenal) + TXT Ret IIBB aplicadas ARBA alta por lote A-122R. Vigente desde 01/03/2026.",
            ),
            # ('other', 'Other')
        ]
    )

    # def action_create_tax_settlement_entry(self):
    #     if self.settlement_tax == 'profits':
    #         self = self.with_context(quincenal=True)
    #     return super(
    #         AccountJournal, self).action_create_tax_settlement_entry()

    def iibb_aplicado_dgr_mendoza_files_values(self, move_lines):
        self.ensure_one()
        ret = ""
        for line in move_lines:
            # Agente de Retención del Impuesto sobre los Ingresos Brutos

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
            content += (line.withholding_id.name or "").rjust(12, "0")[:12]  # we are forcing 12 first numbers always.

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
            ret += content

        # File name
        move_line = move_lines and move_lines[0] or self.env["account.move.line"]
        tipo_agente = "rr"  # This value is fixed just because we are doing the retention txt, when adding the
        # perception we need to change it
        cuit = move_line.company_id.vat
        periodo = fields.Date.from_string(move_line.date).strftime("%Y") or ""  # 'pppp' AÑO '2020'
        cuota = fields.Date.from_string(move_line.date).strftime("%m") or ""  # 'cc'
        return [
            {
                "txt_filename": "%s%s%s%s.txt" % (tipo_agente, cuit, periodo, cuota),
                "txt_content": ret,
            }
        ]

    def _get_perception_original_invoice_number(self, line):
        self.ensure_one()
        res = ""
        related_invoice = line.move_id._found_related_invoice() or line.move_id
        letter = related_invoice.l10n_latam_document_type_id.l10n_ar_letter
        internal_type = related_invoice.l10n_latam_document_type_id.internal_type

        # 2 Tipo de comprobante
        if internal_type == "invoice":
            document_type = letter == "E" and 5 or 1
        elif internal_type == "credit_note":
            document_type = letter == "E" and 106 or 102
        elif internal_type == "debit_note":
            document_type = letter == "E" and 6 or 2
        elif related_invoice.move_type == "out_invoice":
            document_type = 20
        elif related_invoice.move_type == "out_refund":
            document_type = 120
        else:
            raise ValidationError(_("Tipo de comprobante no reconocido"))
        res += str(document_type)[:1]

        # 3 Letra del comprobante
        res += letter

        # 4 Número del comprobante
        res += "%012d" % int(re.sub("[^0-9]", "", related_invoice.l10n_latam_document_number or ""))
        return res

    def iibb_aplicado_api_files_values(self, move_lines):
        """Implementado segun especificación en carpeta doc de este repo"""

        def format_amount(amount, integers, decimals=2):
            # overwrite default format_amount
            template = "%0" + "%ss" % (integers + decimals + 1)
            # TODO se podria mejorar haciendo algo asi pero hace falta
            # hacer parametro el 16
            # "{0:>16.2f}".format(12.1)
            return template % f"{round(amount, decimals):.2f}".replace(".", ",")

        self.ensure_one()
        ret = ""
        perc = ""

        for line in move_lines:
            partner = line.partner_id

            tax = line._get_settlement_tax()

            # 1 - tipo de operacion
            if tax.type_tax_use in ["sale", "purchase"]:
                content = "2"

                # para percepciones ho es obligatorio
                articulo_inciso_calculo = tax.api_articulo_inciso_calculo_percepcion or "000"
                articulo_inciso_retiene = tax.api_codigo_articulo_percepcion
            elif tax.l10n_ar_withholding_payment_type in ["customer", "supplier"]:
                content = "1"

                articulo_inciso_calculo = tax.api_articulo_inciso_calculo_retencion
                articulo_inciso_retiene = tax.api_codigo_articulo_retencion
            else:
                raise ValidationError(_("Tipo de impuesto %s equivocado") % (tax.tax_group_id.name))

            if not articulo_inciso_calculo or not articulo_inciso_retiene:
                raise RedirectWarning(
                    message=_(
                        'Debe establecer la información de "artículo/inciso" en la configuración del impuesto "%s"'
                        'en la solapa "API".',
                        tax.name,
                    ),
                    action={
                        "type": "ir.actions.act_window",
                        "res_model": "account.tax",
                        "views": [(False, "form")],
                        "res_id": tax.id,
                        "name": _("Tax"),
                        "view_mode": "form",
                    },
                    button_text=_("Edit Tax"),
                )

            # 2 - fecha
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # 3 - Código de artículo Inciso por el que retiene
            content += articulo_inciso_retiene

            # 4 - tipo de comprobante y
            # 5 - letra de comprobante
            internal_type = line.l10n_latam_document_type_id.internal_type
            # No se si esto es correcto en 17: si no tiene internal type entonces es pago
            if internal_type:
                move = line.move_id

            if internal_type and internal_type == "invoice":
                # factura
                content += "01" + line.l10n_latam_document_type_id.l10n_ar_letter

            elif internal_type and internal_type == "debit_note":
                # ND
                content += "02" + line.l10n_latam_document_type_id.l10n_ar_letter
            elif internal_type and internal_type == "credit_note":
                content += "10" + line.l10n_latam_document_type_id.l10n_ar_letter
            else:
                # orden de pago (sin letra)
                # 09 sería otro comprobante y 10 reinitegro de perc/ret
                # aclaración: si cargo una nota de crédito con código 10 me aparece un mensaje como este:
                # "Error: Línea 25: Debe ingresar un tipo de comprobante válido.
                # La carga de Reintegro de Retenc./Perc solo se puede efectuar desde el formulario en forma manual. La línea fue descartada."
                content += "03 "

            # 6 - numero comprobante Texto(16)
            if internal_type and internal_type in ("invoice", "credit_note", "debit_note"):
                # TODO el aplicativo deberia empezar a aceptar 5 digitos
                pos, number = get_pos_and_number(move.l10n_latam_document_number)
                # versión 4.0 de siprib release 0 no acepta 5 dígitos aún
                content += f"{pos:>03s}"[-4:]
                content += f"{number:>08s}"
                content += "    "
            else:
                content += "%016s" % (line.withholding_id.name or "")

            # 7 - fecha comprobante
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # 8 - monto comprobante
            content += (
                format_amount(abs(line.move_id.amount_total_signed), 12, 2)
                if line.move_id.is_invoice()
                else format_amount(abs(-line.balance), 12, 2)
            )

            # 9 - tipo de documento
            # nosotros solo permitimos CUIT por ahora
            # Revisar
            content += "3"

            # 10 - numero de documento
            content += partner.ensure_vat()

            # 11 - Condición frente a Ingresos Brutos
            # 1 es inscripto, 2 no inscripto con oblig. a insc y 3 no insc sin
            # oblig a insc. TODO implementar 2
            gross_income_type = partner.l10n_ar_gross_income_type
            if not gross_income_type:
                raise ValidationError(
                    _('Debe setear el tipo de inscripción de IIBB del partner "%s" (id: %s)')
                    % (partner.name, partner.id)
                )
            if gross_income_type in ["multilateral", "local"]:
                content += "1"
            else:
                content += "3"

            # 12 - Número de Inscripción en Ingresos Brutos
            content += (re.sub("[^0-9]", "", partner.l10n_ar_gross_income_number or "")).rjust(10, "0")

            # 13 - Situación frente a IVA donde:
            # ri (1), rni (2), exento (3), monotr (4)
            res_iva = partner.l10n_ar_afip_responsibility_type_id
            if res_iva.code in ["1", "1FM"]:
                # RI
                content += "1"
            elif res_iva.code == "2":
                # RNI
                content += "2"
            elif res_iva.code == "4":
                # EXENTO
                content += "3"
            elif res_iva.code == "6":
                # MONOT
                content += "4"
            else:
                raise ValidationError(
                    _('La responsabilidad frente a IVA "%s" no está soportada para ret/perc Santa Fe') % res_iva.name
                )

            # 14 - Marca inscripción Otros Gravámenes
            # TODO implementar (requiere nuevo campo en odoo?)
            content += "0"

            # 15 - Marca Inscripción DREI
            # TODO revisar si implementamos o no, aparentemente este campo
            # activo en drei no se usa o no es lo que esperamos, por ahora
            # no lo hacemos requerido para no andar molestando al dope
            # if not partner.drei:
            #     raise ValidationError(_(
            #         'Debe seleccionar situación DREI para partner '
            #         '"%s" (id: %s)') % (
            #             partner.name, partner.id))
            content += partner.drei == "activo" and "1" or "0"

            # 16 - Importe Otros Gravámenes
            # TODO implementar
            content += format_amount(0.0, 10, 2)

            # 17 - Importe IVA (solo si factura)
            if line.move_id.is_invoice():
                amounts = line.move_id._l10n_ar_get_amounts(company_currency=True)
                vat_amount = amounts["vat_amount"]
                base_amount = amounts["vat_taxable_amount"]
            else:
                vat_amount = 0.0
                base_amount = line.payment_id and line.withholding_id.base_amount or 0.0
            content += format_amount(vat_amount, 10, 2)

            # 18 - Base Imponible para el cálculo
            # tal vez la base deberiamos calcularlo asi, en pagos no porque
            # los asientos estan separados
            # content += format_amount(-get_line_tax_base(line), 12, 2, ',')
            content += format_amount(base_amount, 12, 2)

            # 19 - Alícuota / alicuota
            content += format_amount(tax.amount, 2, 2)

            # 20 - Impuesto Determinado
            content += format_amount(abs(-line.balance), 12, 2)

            # 21 - Derecho Registro e Inspección
            # TODO implementar
            # es un importe seguramente importe retenido de drei
            content += format_amount(0.0, 9, 2)

            # 22 - Monto Retenido
            # TODO por ahora es igual a impuesto determinado pero, podria ser
            # distinto en algún caso?
            content += format_amount(abs(-line.balance), 12, 2)

            # 23 - Artículo/Inciso para el cálculo
            content += articulo_inciso_calculo

            # 24 - Tipo de Exención
            # TODO implementar. Por ahora no implementamos excenciones ya que
            # a priori no las informan
            content += "0"

            # 25 - Año de Exención
            # TODO implementar
            content += "0000"

            # 26 - Número de Certificado de Exención
            # TODO implementar
            content += "      "

            # 27 - Número de Certificado Propio
            # TODO implementar
            content += "            "

            # new line
            content += "\r\n"

            if tax.type_tax_use in ["sale", "purchase"]:
                perc += content
            elif tax.l10n_ar_withholding_payment_type in ["customer", "supplier"]:
                ret += content

        # return [
        #     {
        #         'txt_filename': 'Perc IIBB API Aplicadas.txt',
        #         'txt_content': perc,
        #     },
        #     {
        #         'txt_filename': 'Ret IIBB API Aplicadas.txt',
        #         'txt_content': ret,
        #     }
        return [
            {
                "txt_filename": "Perc/Ret IIBB API Aplicadas.txt",
                "txt_content": perc + ret,
            }
        ]

    def iibb_aplicado_agip_files_values(self, move_lines):  # noqa: C901
        """Ver readme del modulo para descripcion del formato. Tambien
        archivos de ejemplo en /doc
        """
        self.ensure_one()

        ret_perc = ""
        credito = ""

        company_currency = self.company_id.currency_id
        backward_comp_is_installed = self.env["ir.module.module"].search(
            [("name", "=", "l10n_ar_tax_settlement_backward_comp"), ("state", "=", "installed")]
        )
        for line in move_lines.filtered("amount_currency").sorted("date"):
            # pay_group = payment.payment_group_id
            move = line.move_id
            payment = line.payment_id
            # implementamos esto que teniamos en agip para obtener alicuota de rectificativa
            date = line.move_id._found_related_invoice().date or line.date
            tax = line._get_settlement_tax(date=date)
            partner = line.partner_id
            internal_type = line.l10n_latam_document_type_id.internal_type

            if not partner.vat:
                raise ValidationError(
                    _('El partner "%s" (id %s) no tiene número de identificación establecido')
                    % (partner.name, partner.id)
                )
            alicuot = tax.amount

            ret_perc_applied = False
            es_percepcion = False
            # 1 - Tipo de Operación
            if tax.type_tax_use in ["sale", "purchase"]:
                # tax.amount_type == 'partner_tax':
                es_percepcion = True
                content = "2"
            elif tax.l10n_ar_withholding_payment_type in ["customer", "supplier"]:
                # tax.withholding_type == 'partner_tax':
                content = "1"

            # notas de credito
            if internal_type == "credit_note":
                # 2 - Nro. Nota de crédito
                content += "%012d" % int(re.sub("[^0-9]", "", move.l10n_latam_document_number or ""))

                # 3 - Fecha Nota de crédito
                content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

                # 4 - Monto nota de crédito
                # TODO implementar devoluciones de pagos
                # content += format_amount(
                #     line.move_id.cc_amount_total, 16, 2, ',')
                # la especificacion no lo dice claro pero un errror al importar
                # si, lo que se espera es el importe base, ya que dice que
                # este, multiplicado por la alícuota, debe ser igual al importe
                # a retener/percibir
                taxable_amount = line.tax_base_amount
                content += format_amount(taxable_amount, 16, 2, ",")

                # 5 - Nro. certificado propio
                # opcional y el que nos pasaron no tenia
                content += "                "

                # segun interpretamos de los daots que nos pasaron 6, 7, 8 y 11
                # son del comprobante original
                or_inv = line.move_id._found_related_invoice()
                if not or_inv:
                    raise ValidationError(
                        _(
                            "No pudimos encontrar el comprobante original para %s "
                            '(id %s). Verifique que en la nota de crédito "%s", el'
                            " campo origen es el número de la factura original"
                        )
                        % (line.move_id.display_name, line.move_id.id, line.move_id.display_name)
                    )

                # 6 - Tipo de comprobante origen de la retención

                # Identificamos si el comprobante de origen es una Factura de credito MiPyMEs sino lo
                # tratamos como una factura normal
                # NOTA: Esto solo aplica para el calculo de Percepciones
                content += "10" if or_inv.l10n_latam_document_type_id.code in ["201", "206", "211"] else "01"

                # 7 - Letra del Comprobante
                if payment:
                    content += " "
                else:
                    content += or_inv.l10n_latam_document_type_id.l10n_ar_letter

                # 8 - Nro de comprobante (original)
                content += "%016d" % int(re.sub("[^0-9]", "", or_inv.l10n_latam_document_number or ""))

                # 9 - Nro de documento del Retenido
                content += str(partner._get_id_number_sanitize())

                # 10 - Código de norma
                # por ahora solo padron regimenes generales
                content += "029"

                # 11 - Fecha de retención/percepción
                content += fields.Date.from_string(or_inv.invoice_date).strftime("%d/%m/%Y")

                # 12 - Ret/percep a deducir

                # si la línea tiene moneda diferente de la moneda de la compañía queremos que la ret/perc
                # se calcule aplicando la alícuota sobre la base imponible en la moneda de la compañía
                if line.currency_id and line.currency_id != line.company_id.currency_id:
                    ret_perc_applied = float_round((taxable_amount * alicuot / 100), precision_digits=2)
                content += format_amount((line.balance if not ret_perc_applied else ret_perc_applied), 16, 2, ",")

                # 13 - Alícuota
                content += format_amount(alicuot, 5, 2, ",")

                content += "\r\n"

                credito += content
                continue

            # 2 - Código de Norma
            # por ahora solo padron regimenes generales
            content += "029"

            # 3 - Fecha de retención/percepción
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # 4 - Tipo de comprobante origen de la retención
            if internal_type == "invoice":
                content += "10" if line.move_id.l10n_latam_document_type_id.code in ["201", "206", "211"] else "01"
            elif internal_type == "debit_note":
                if es_percepcion:
                    content += "09"
                else:
                    content += "02"
            else:
                # orden de pago
                content += "03"

            # 5 - Letra del Comprobante
            # segun vemos en los archivos de ejemplo solo en percepciones
            if payment:
                content += " "
            else:
                content += line.l10n_latam_document_type_id.l10n_ar_letter if internal_type == "invoice" else " "

            # 6 - Nro de comprobante
            content += "%016d" % int(
                re.sub("[^0-9]", "", re.sub(r"\s\(\d+\)$", "", move.l10n_latam_document_number or ""))
            )
            # 7 - Fecha del comprobante
            content += fields.Date.from_string(move.date).strftime("%d/%m/%Y")

            # obtenemos montos de los comprobantes
            if payment:
                # solo en comprobantes A, M segun especificacion
                vat_amount = 0.0
                total_amount = float_round(payment.move_id.amount_total_in_currency_signed, precision_digits=2)
                if backward_comp_is_installed and payment.is_backward_withholding_payment:
                    # Buscamos los payments sin retención que vienen migrados de la versión anterior y le sumamos
                    # el amount total de los mismos (move_id.amount_total_in_currency_signed) al total_amount de la
                    # retención. Esto lo hacemos porque en la migración de 16 a 18 se migran los pagos y las retenciones
                    # por separado a diferencia de 16 que estaba todo en el mismo asiento.
                    # Contemplamos que en el nombre puede haber sufijos automáticos tipo " (2)" (por ejemplo)
                    payment_name = re.sub(r"\s\(\d+\)$", "", payment.name)
                    related_payments = self.env["account.payment"].search(
                        [
                            "|",
                            ("name", "=", payment_name),
                            ("name", "=like", payment_name + " (%)"),
                            ("company_id", "=", payment.company_id.id),
                            ("partner_id", "=", payment.partner_id.id),
                            ("id", "!=", payment.id),
                            ("state", "in", ["paid", "in_process"]),
                        ]
                    )
                    if related_payments:
                        total_amount += float_round(
                            sum(related_payments.mapped("move_id.amount_total_in_currency_signed")), precision_digits=2
                        )
                # es lo mismo que payment_group.matched_amount_untaxed
                taxable_amount = float_round(line.withholding_id.base_amount, precision_digits=2)

                # lo sacamos por diferencia
                other_taxes_amount = company_currency.round(total_amount - taxable_amount - vat_amount)
            elif line.move_id.is_invoice():
                amounts = line.move_id._l10n_ar_get_amounts(company_currency=True)
                # segun especificacion el iva solo se reporta para estos
                if line.l10n_latam_document_type_id.l10n_ar_letter in ["A", "M"]:
                    vat_amount = amounts["vat_amount"]
                else:
                    vat_amount = 0.0

                total_amount = (1 if line.move_id.is_inbound() else -1) * line.move_id.amount_total_signed

                # por si se olvidaron de poner agip en una linea de factura
                # la base la sacamos desde las lineas de impuesto
                # taxable_amount = line.move_id.cc_amount_untaxed
                taxable_amount = line.tax_base_amount

                # tambien lo sacamos por diferencia para no tener error (por el
                # calculo trucado de taxable_amount por ejemplo) y
                # ademas porque el iva solo se reporta si es factura A, M
                other_taxes_amount = company_currency.round(total_amount - taxable_amount - vat_amount)
                # other_taxes_amount = line.move_id.cc_other_taxes_amount
            else:
                raise ValidationError(_("El impuesto no está asociado"))

            # 8 - Monto del comprobante
            content += format_amount(total_amount, 16, 2, ",")

            # 9 - Nro de certificado propio
            content += (line.withholding_id.name or "").rjust(16, " ")

            # 10 - Tipo de documento del Retenido
            # vat
            if partner.l10n_latam_identification_type_id.name not in ["CUIT", "CUIL", "CDI"]:
                raise ValidationError(
                    _(
                        'EL el partner "%s" (id %s), el tipo de identificación'
                        "debe ser una de siguientes: CUIT, CUIL, CDI."
                    )
                    % (partner.id, partner.name)
                )
            doc_type_mapping = {"CUIT": "3", "CUIL": "2", "CDI": "1"}
            content += doc_type_mapping[partner.l10n_latam_identification_type_id.name]

            # 11 - Nro de documento del Retenido
            content += str(partner._get_id_number_sanitize())

            # 12 - Situación IB del Retenido
            # 1: Local 2: Convenio Multilateral
            # 4: No inscripto 5: Reg.Simplificado
            if not partner.l10n_ar_gross_income_type:
                raise ValidationError(
                    _('Debe setear el tipo de inscripción de IIBB del partner "%s" (id: %s)')
                    % (partner.name, partner.id)
                )

            # ahora se reportaria para cualquier inscripto el numero de cuit
            gross_income_mapping = {"local": "5", "multilateral": "2", "exempt": "4"}
            content += gross_income_mapping[partner.l10n_ar_gross_income_type]

            # 13 - Nro Inscripción IB del Retenido
            if partner.l10n_ar_gross_income_type == "exempt":
                content += "00000000000"
            else:
                content += partner.ensure_vat()

            # 14 - Situación frente al IVA del Retenido
            # 1 - Responsable Inscripto
            # 3 - Exento
            # 4 - Monotributo
            res_iva = partner.l10n_ar_afip_responsibility_type_id
            if res_iva.code in ["1", "1FM"]:
                # RI
                content += "1"
            elif res_iva.code == "4":
                # EXENTO
                content += "3"
            elif res_iva.code == "6":
                # MONOT
                content += "4"
            else:
                raise ValidationError(
                    _('La responsabilidad frente a IVA "%s" no está soportada para ret/perc AGIP') % res_iva.name
                )

            # 15 - Razón Social del Retenido
            content += f"{partner.name:30.30}"

            # 16 - Importe otros conceptos
            content += format_amount(other_taxes_amount, 16, 2, ",")

            # 17 - Importe IVA
            content += format_amount(vat_amount, 16, 2, ",")

            # 18 - Monto Sujeto a Retención/ Percepción
            content += format_amount(taxable_amount, 16, 2, ",")

            # 19 - Alícuota
            content += format_amount(alicuot, 5, 2, ",")

            # 20 - Retención/Percepción Practicada

            # si la línea tiene moneda diferente de la moneda de la compañía queremos que la ret/perc
            # se calcule aplicando la alícuota sobre la base imponible en la moneda de la compañía
            if line.currency_id and line.currency_id != line.company_id.currency_id:
                ret_perc_applied = float_round((taxable_amount * alicuot / 100), precision_digits=2)
            content += format_amount((-line.balance if not ret_perc_applied else ret_perc_applied), 16, 2, ",")

            # 21 - Monto Total Retenido/Percibido
            content += format_amount((-line.balance if not ret_perc_applied else ret_perc_applied), 16, 2, ",")

            # # 22 - Aceptacion
            content += " "

            # 24 - Fecha Aceptación "Expresa"
            content += "          "

            content += "\r\n"

            ret_perc += content

        return [
            {
                "txt_filename": "Perc/Ret IIBB AGIP Aplicadas.txt",
                "txt_content": ret_perc,
            },
            {
                "txt_filename": "NC Perc/Ret IIBB AGIP Aplicadas.txt",
                "txt_content": credito,
            },
        ]

    def iibb_aplicado_act_7_files_values(self, move_lines):
        return self.iibb_aplicado_files_values(move_lines, act_7=True)

    def iibb_aplicado_files_values(self, move_lines, act_7=None):
        """
        Por ahora es el de arba, renombrar o generalizar para otros
        Implementado segun esta especificacion
        https://drive.google.com/file/d/0B3trzV0e2WzveHhBTk9xWEl6RjA/view
        Implementados:
            - 1.2 Percepciones Act. 7 método Percibido (quincenal)
            - 1.7 Retenciones ( excepto actividad 26, 6 de Bancos y 17 de
            Bancos y No Bancos)
        """
        self.ensure_one()
        ret = ""
        perc = ""

        for line in move_lines:
            # pay_group = payment.payment_group_id
            move = line.move_id
            payment = line.payment_id
            internal_type = line.l10n_latam_document_type_id.internal_type
            document_code = line.l10n_latam_document_type_id.code

            line.partner_id.ensure_vat()

            content = line.partner_id.l10n_ar_formatted_vat
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # solo para percepciones
            if not payment:
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
                content += line.l10n_latam_document_type_id.l10n_ar_letter
            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number, move.l10n_latam_document_type_id.code
            )
            # si el punto de venta es de 5 digitos no encontramos doc
            # que diga como proceder, tomamos los ultimos 4 digitos
            pto_venta = "{:0>4d}".format(document_parts["point_of_sale"])[-4:]
            nro_documento = "{:0>8d}".format(document_parts["invoice_number"])[-8:]
            content += str(pto_venta)
            content += str(nro_documento)

            # solo para percepciones
            if not payment:
                content += format_amount(-get_line_tax_base(line), 12, 2, ",")

            # este es para el primer tipo de la especificación
            content += format_amount(-line.balance, 11, 2, ",")

            # solo para percepciones
            # según especificación se requiere fecha nuevamente
            # por ahora lo sacamos ya que en ticket 16448 nos mandaron ej.
            # donde no se incluía, en realidad tal vez depende de la actividad
            # ya que en la primer tabla del pdf la agrega y en la segunda no
            if act_7 and not payment:
                content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")
            content += "A"
            content += "\r\n"

            if payment:
                ret += content
            else:
                perc += content

        # para la fecha de la presentación tomamos la fecha de un apunte a liquidar
        # el valor de la quincena puede ser 0, 1, 2. deberiamos ver si podemos
        # completarlo de alguna manera
        period = move_lines and fields.Date.from_string(move_lines[0].date).strftime("%Y%mX") or ""

        # AR-CUIT-PERIODO-ACTIVIDAD-LOTE_MD5
        perc_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat,
            period,
            "7",  # 7 serian las percepciones
        )

        # AR-vat-PERIODO-ACTIVIDAD-LOTE_MD5
        ret_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat,
            period,
            "6",  # 6 serian las retenciones
        )

        return [
            {
                "txt_filename": perc_txt_filename,
                "txt_content": perc,
            },
            {
                "txt_filename": ret_txt_filename,
                "txt_content": ret,
            },
        ]

    def iibb_aplicado_sircar_files_values(self, move_lines):
        """Especificacion en /doc/sircar, solicitado en ticket 62526"""
        self.ensure_one()
        ret = ""
        perc = ""

        for line in move_lines.filtered(lambda x: not x.payment_id and not x.move_id):
            raise ValidationError(
                _(
                    "Hay lineas a liquidar que no estan enlazadas a pagos ni "
                    "facturas lo cual es requerido para generar el TXT"
                )
            )

        line_nbr = 1
        for line in move_lines.filtered("payment_id"):
            tax = line._get_settlement_tax()
            alicuot = tax.amount

            payment = line.payment_id
            internal_type = line.l10n_latam_document_type_id.internal_type

            # 1 Número de Renglón (único por archivo)
            content = []
            content.append("%05d" % line_nbr)

            # 2 Origen del Comprobante
            content.append("1")

            # 3 Tipo del Comprobante
            if payment.payment_type == "outbound":
                content.append("1")
            else:
                content.append("2")

            # 4 Número del comprobante
            content.append("%012d" % int(re.sub("[^0-9]", "", line.name or "")))

            # 5 Cuit del contribuyene
            content.append(line.partner_id.ensure_vat())

            # 6 Fecha de la percepción
            content.append(fields.Date.from_string(line.date).strftime("%d/%m/%Y"))

            # 7 Monto sujeto a percepción
            content.append(format_amount(line.withholding_id.base_amount, 12, 2, "."))

            # 8 alicuota de la retencion
            content.append(format_amount(alicuot, 6, 2, "."))

            # 9 Monto retenido
            content.append(format_amount(-line.balance, 12, 2, "."))

            # 10 Tipo de Régimen de Percepción
            # (código correspondiente según tabla definida por la jurisdicción)
            if not tax.l10n_ar_code:
                raise RedirectWarning(
                    message=_(
                        "No hay régimen de retencion (Código AFIP 'l10n_ar_code') configurado para el impuesto: '%(tax_name)s'.",
                        tax_name=tax.name,
                    ),
                    action=tax.get_formview_action(),
                    button_text=_("Edit Tax"),
                )
            content.append(tax.l10n_ar_code)

            # 11 Jurisdicción: código en Convenio Multilateral de la
            # jurisdicción a la cual está presentando la DDJJ
            if not tax.l10n_ar_state_id or not tax.l10n_ar_state_id.jurisdiction_code:
                raise RedirectWarning(
                    message=_(
                        "No hay jurisdicción establecida en el impuesto '%(tax_name)s' o no tiene código de jurisdicción.",
                        tax_name=tax.name,
                    ),
                    action=tax.get_formview_action(),
                    button_text=_("Edit Tax"),
                )

            content.append(tax.l10n_ar_state_id.jurisdiction_code)

            # Tipo registro 2. Provincia Cordoba
            if tax.l10n_ar_state_id.jurisdiction_code in ["904", "914"]:
                # 12 Tipo de Operación (1-Efectuada, 2-Anulada, 3-Omitida)
                content.append("2" if internal_type == "credit_note" else "1")

                # 13 Fecha de Emisión de Constancia (en formato dd/mm/aaaa)
                content.append(fields.Date.from_string(line.date).strftime("%d/%m/%Y"))

                # 14 Número de Constancia - Numeric(14)
                content.append("%014s" % int(re.sub("[^0-9]", "", line.withholding_id.name or "0")[:14]))

                # 15 Número de Constancia original (sólo para las Anulaciones –ver códigos por jur-)  - Numeric(14)
                original_invoice = line.move_id._found_related_invoice() or line.move_id
                content.append(
                    "%014d" % int(re.sub("[^0-9]", "", original_invoice.document_number or ""))
                    if internal_type == "credit_note"
                    else "%014d" % 0
                )

            ret += ",".join(content) + "\r\n"
            line_nbr += 1

        line_nbr = 1
        for line in move_lines.filtered(lambda x: x.move_id.is_invoice()):
            tax = line._get_settlement_tax()
            alicuot = tax.amount

            # 1 Número de Renglón (único por archivo)
            content = []
            content.append("%05d" % line_nbr)

            letter = line.l10n_latam_document_type_id.l10n_ar_letter

            # 2 Tipo de comprobante
            internal_type = line.l10n_latam_document_type_id.internal_type
            if internal_type == "invoice":
                tipo_comprobante = letter == "E" and 5 or 1
            elif internal_type == "credit_note":
                tipo_comprobante = letter == "E" and 106 or 102
            elif internal_type == "debit_note":
                tipo_comprobante = letter == "E" and 6 or 2
            elif line.move_id.type == "out_invoice":
                tipo_comprobante = 20
            elif line.move_id.type == "out_refund":
                tipo_comprobante = 120
            else:
                raise ValidationError(_("Tipo de comprobante no reconocido"))
            content.append("%03d" % tipo_comprobante)

            # 3 Letra del comprobante
            content.append(line.l10n_latam_document_type_id.l10n_ar_letter)

            # 4 Número del comprobante
            content.append("%012d" % int(re.sub("[^0-9]", "", line.move_id.l10n_latam_document_number or "")))

            # 5 Cuit del contribuyene
            content.append(line.partner_id.ensure_vat())

            # 6 Fecha de la percepción
            content.append(fields.Date.from_string(line.date).strftime("%d/%m/%Y"))

            # 7 Monto sujeto a percepción
            content.append(format_amount(-get_line_tax_base(line), 12, 2, "."))

            # 8 alicuota de la percepcion
            content.append(format_amount(alicuot, 6, 2, "."))

            # 9 Monto percibido
            content.append(format_amount(-line.balance, 12, 2, "."))

            # 10 Tipo de Régimen de Percepción
            # (código correspondiente según tabla definida por la jurisdicción)
            if not tax.l10n_ar_code:
                raise RedirectWarning(
                    message=_(
                        "No hay régimen de percepción (Código AFIP 'l10n_ar_code') configurado para el impuesto: '%(tax_name)s'.",
                        tax_name=tax.name,
                    ),
                    action=tax.get_formview_action(),
                    button_text=_("Edit Tax"),
                )
            content.append(tax.l10n_ar_code)

            # 11 Jurisdicción: código en Convenio Multilateral de la
            # jurisdicción a la cual está presentando la DDJJ
            if not tax.l10n_ar_state_id or not tax.l10n_ar_state_id.jurisdiction_code:
                raise RedirectWarning(
                    message=_(
                        "No hay jurisdicción establecida en el impuesto '%(tax_name)s' o no tiene código de jurisdicción.",
                        tax_name=tax.name,
                    ),
                    action=tax.get_formview_action(),
                    button_text=_("Edit Tax"),
                )

            content.append(tax.l10n_ar_state_id.jurisdiction_code)

            # Tipo registro 2. Provincia Cordoba
            if tax.l10n_ar_state_id.jurisdiction_code in ["904", "914"]:
                # 12 Tipo de Operación (1-Efectuada, 2-Anulada, 3-Omitida, 4-Informativa)
                content.append("2" if internal_type == "credit_note" else "1")

                # 13 Número de Constancia original (sólo para 2-Anulaciones) Alfanumérico (14) - ejemplo 1A002311312221
                content.append(
                    self._get_perception_original_invoice_number(line)
                    if internal_type == "credit_note"
                    else "%014d" % 0
                )

            perc += ",".join(content) + "\r\n"
            line_nbr += 1

        return [
            {
                "txt_filename": "Perc IIBB Aplicadas para SIRCAR.txt",
                "txt_content": perc,
            },
            {
                "txt_filename": "Ret IIBB Aplicadas para SIRCAR.txt",
                "txt_content": ret,
            },
        ]

    def iibb_sufrido_files_values(self, move_lines):
        """
        Especificación según:
        https://drive.google.com/file/d/0B3trzV0e2WzvUjB1MnhXT0VteFE/view
        y ej. de excel acá
        http://www.ca.gov.ar/descargar/sifere/importaciones_sifere.xls

        tal vez querramos agregar chequeo de que es "sifere" viendo que es
        cia multilateral

        * el txt generado se puede probar en este aplicativo de pruebas
        http://www.ca.gov.ar/descargar/sifereweb/SifereClientAppDEDUCCIONES.zip

        * para consultas directo a sifere mesa de ayuda enviar correo electronico a
        sifereweb@comisionarbitral.gob.ar
        """
        self.ensure_one()

        ret = ""
        perc = ""
        desp_imp = ""
        for line in move_lines:
            if line.l10n_latam_document_type_id.code in ["66", "67"]:
                desp_imp += " - " + line.move_id.display_name + "\n"
                continue
            payment = line.payment_id
            # pay_group = payment.payment_group_id
            move = line.move_id
            internal_type = line.l10n_latam_document_type_id.internal_type

            if not line.partner_id:
                raise ValidationError(
                    _('La percepción %s (id: %d) del comprobante "%s" (id: %d) no tiene partner asociado.')
                    % (line.withholding_id.name, line.id, line.move_id.name, line.move_id.id)
                )
            line.partner_id.ensure_vat()

            tax = line._get_settlement_tax()
            content = tax.l10n_ar_state_id.jurisdiction_code or "000"
            content += line.partner_id.l10n_ar_formatted_vat
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # en las retenciones, el numero de comprobante debe ser de 16
            # digitos y ademas sacamos estos datos del pago y no del nro de doc
            # del payment group
            if payment:
                if float_round(line.balance, precision_digits=2) == 0.0:
                    # si el monto de la retencion es 0.0 no lo incluimos en el txt
                    continue

                # el numero de la retencion
                pos, number = get_pos_and_number(line.withholding_id.name)
                content += f"{pos:>04s}"
                content += f"{number:>016s}"
            else:
                document_parts = move._l10n_ar_get_document_number_parts(
                    move.l10n_latam_document_number, move.l10n_latam_document_type_id.code
                )
                pos = document_parts["point_of_sale"]
                number = document_parts["invoice_number"]
                # si el punto de venta es de 5 digitos no encontramos doc
                # que diga como proceder, tomamos los ultimos 4 digitos
                pto_venta = "{:0>4d}".format(document_parts["point_of_sale"])[-4:]
                nro_documento = "{:0>8d}".format(document_parts["invoice_number"])[-8:]
                content += pto_venta
                content += nro_documento

            # si es pago es R, si no es la letra del comprobante u Otros
            if payment:
                content += "R"
                # la letra tiene que ser A, B, C, E, M ó bien Espacio, en caso
                # de pago tenemox X, mandamos espacio
                content += " "
            else:
                # por lo que vimos en sos-contador, si es ticket se pasa
                # como factura
                doc_type = (
                    internal_type in ["invoice", "ticket"]
                    and "F"
                    or internal_type == "credit_note"
                    and "C"
                    or internal_type == "debit_note"
                    and "D"
                    or internal_type == "receipt_invoice"
                    and "R"
                    or "O"
                )
                # si es ticket y es negativo entonces en NC (TODO) cambiar
                # si ya implementamos nc de ticket de otra manera
                if internal_type == "ticket" and line.balance < 0.0:
                    doc_type = "credit_note"
                content += doc_type
                if doc_type == "O":
                    content += " "
                else:
                    content += line.l10n_latam_document_type_id.l10n_ar_letter or " "

            # en retencíones hay que poner el número de comprobante original
            # pero solo en digitos
            if payment:
                content += "%020d" % int(re.sub("[^0-9]", "", move.l10n_latam_document_number))
            content += format_amount(line.balance, 11, 2, ",")
            content += "\r\n"

            if payment:
                ret += content
            else:
                perc += content

        if desp_imp:
            desp_imp = (
                "En los registros seleccionados encontramos algunos despachos de importación, los mismos deben"
                "cargarse a mano. Los registros despachos corrspondientes son:\n"
            ) + desp_imp
        return [
            {
                "txt_filename": "Percepciones sufridas SIFERE.txt",
                "txt_content": perc,
            },
            {
                "txt_filename": "Retenciones sufridas SIFERE.txt",
                "txt_content": ret,
            },
            {
                "txt_filename": "Despachos de importación (no importar).txt",
                "txt_content": desp_imp,
            },
        ]

    def sicore_aplicado_files_values(self, move_lines):
        self.ensure_one()

        # build txt file
        content = ""

        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            partner = line.partner_id
            if not partner.l10n_latam_identification_type_id.l10n_ar_afip_code:
                raise ValidationError(
                    _('EL tipo de identificación "%s" no tiene código de arca configurado')
                    % (partner.l10n_latam_identification_type_id.name)
                )
            if not partner.vat:
                raise ValidationError(
                    _('El partner "%s" (id %s) no tiene número de identificación establecido')
                    % (partner.name, partner.id)
                )

            payment = line.payment_id
            move = line.move_id

            # si tengo payment es una retención, sino es una percepción y tengo que sacar la información de la factura (del move)
            if payment:
                # Codigo del Comprobante         [ 2]
                content += (
                    (payment.payment_type == "inbound" and "02")
                    or (payment.payment_type == "outbound" and "06")
                    or "00"
                )

                # Fecha Emision Comprobante      [10] (dd/mm/yyyy)
                content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")
                # Numero Comprobante            [16]
                content += "%016d" % int(re.sub("[^0-9]", "", move.l10n_latam_document_number))
                # Importe del comprobante
                codop = "1"
                issue_date = payment.date
                amount_tot = abs(payment.payment_total)
                base_amount = line.withholding_id.base_amount

            elif move.is_invoice():
                # Codigo del Comprobante         [ 2]
                tipodoc = int(move.l10n_latam_document_type_id.code)
                es_nc = False

                if tipodoc in [1, 6, 19, 51, 81, 82, 118, 201, 206]:
                    # Factura
                    content += "01"
                elif tipodoc in [4, 9, 54]:
                    # Recibo
                    content += "02"
                elif tipodoc in [3, 8, 21, 53, 43, 44, 110, 112, 113, 114, 119, 203, 208]:
                    # Nota de Crédito
                    content += "03"
                    es_nc = True
                elif tipodoc in [2, 7, 20, 52, 45, 46, 115, 116, 120, 202, 207]:
                    # Nota de Débito
                    content += "04"
                else:
                    # Otro comprobante
                    content += "05"

                # Fecha Emision Comprobante      [10] (dd/mm/yyyy)
                content += fields.Date.from_string(move.invoice_date).strftime("%d/%m/%Y")
                # Numero Comprobante            [16]
                # content += '%016d' % int(re.sub('[^0-9]', '', move.l10n_latam_document_number))
                content += "%05d" % int(re.sub("[^0-9]", "", move.l10n_latam_document_number)[:5])
                content += "%011d" % int(re.sub("[^0-9]", "", move.l10n_latam_document_number)[5:])
                issue_date = move.invoice_date
                # si la percepción es sobre una nota de crédito informamos el importe de la percepción
                # aclaración: no tenemos ningún respaldo documental respecto a esto, solo lo hicimos para
                # solucionar la inconsistencia del ticket 61671
                base_amount = line.tax_base_amount if es_nc == False else line.balance
                codop = "2"
                # Importe del comprobante
                amount_tot = abs(move.amount_total_signed)

            # Importe Comprobante            [16]
            content += "%016.2f" % amount_tot
            # Codigo de Impuesto             [ 4]
            # Codigo de Regimen              [ 3]
            codcond = "01"

            tax = line._get_settlement_tax()
            if tax.l10n_ar_withholding_payment_type:
                # 01 --> retención ganancias
                if tax.l10n_ar_tax_type in ["earnings", "earnings_scale"]:
                    content += "0217"
                    regimen = tax.l10n_ar_code
                    # necesitamos lo de filter porque hay dos regimenes que le
                    # agregamos caracteres
                    content += regimen and "%03d" % int("".join(filter(str.isdigit, str(regimen)))) or "000"
                # 02 --> retención iva
                else:
                    content += "0767"
                    # por ahora el unico implementado es para factura M
                    content += "%03d" % int(tax.l10n_ar_code) if tax.l10n_ar_code else "499"
                    if tax.l10n_ar_code == "602":
                        codcond = "13" if tax.amount == 3 else "14"
                    # Si el código de régimen es 214 entonces el código de condición debe ser '00'.
                    # Más información en archivo l10n_ar_account_tax_settlement/data/relaciones-codigos-sicore.csv
                    if tax.l10n_ar_code == "214":
                        codcond = "00"
            else:
                # Percepción de IVA
                content += "0767"
                content += "%03d" % int(
                    tax.l10n_ar_code
                )  # (ver account tax) DUDA cómo le aplico el código de régimen a las facturas viejas
                if tax.l10n_ar_code == "602":
                    codcond = "13" if tax.amount == 3 else "14"
                # Si el código de régimen es 493 entonces el código de condición debe ser '00'.
                # Más información en archivo l10n_ar_account_tax_settlement/data/relaciones-codigos-sicore.xlsx
                elif tax.l10n_ar_code == "493":
                    codcond = "00"

            # Codigo de Operacion            [ 1]
            content += codop  # TODO: ???? DUDA: SERÍA PARA VER SI ES RETENCION O PERCEPCION

            # Base de Calculo                [14]
            content += "%014.2f" % base_amount

            # Fecha Emision Retencion        [10] (dd/mm/yyyy)
            content += fields.Date.from_string(issue_date).strftime("%d/%m/%Y")

            # Codigo de Condicion            [ 2]
            content += codcond  # TODO: ???? ver tabla de condición sicore

            # Retención Pract. a Suj. ..     [ 1]
            content += "0"  # TODO: ????

            # Importe de Retencion           [14] (también se usa para importe de percepción)
            content += "%014.2f" % abs(line.balance)

            # Porcentaje de Exclusion        [ 6]
            content += "%06.2f" % tax.porcentaje_exclusion or "000.00"

            # Fecha Emision Boletin          [10] (dd/mm/yyyy)
            content += fields.Date.from_string(issue_date).strftime("%d/%m/%Y")

            # Tipo Documento Retenido        [ 2]
            content += "%02d" % int(partner.l10n_latam_identification_type_id.l10n_ar_afip_code)

            # Numero Documento Retenido      [20]
            vat = re.sub(r"\D", "", partner.vat)
            content += vat.ljust(20)

            # Numero Certificado Original    [14]
            content += "%014d" % 0  # TODO: ????

            content += "\r\n"

        return [
            {
                "txt_filename": "SICORE Aplicado.txt",
                # 'txt_filename': 'SICORE_%s_%s_%s.txt' % (
                #     re.sub(r'[^\d\w]', '', self.company_id.name),
                #     self.from_date, self.to_date),
                "txt_content": content,
            }
        ]

    def drei_aplicado_files_values(self, move_lines):
        """Implementado segun especificación indicada en ticket 39347. También se puede ver detalles en readme"""
        self.ensure_one()
        content = ""
        for line in move_lines.sorted(key=lambda r: (r.date, r.id)):
            if line.payment_id:
                date = line.payment_id.date
                # cuit (req): 11
                content += line.partner_id.ensure_vat()
                # razon_soc (req): 80
                content += line.partner_id.name.ljust(80)[:80]
                # nro_certificado: 10
                content += "%010d" % int(line.withholding_id.name)
                # fecha_ret: 10 (formato "dd/mm/aaaa")
                content += fields.Date.from_string(date).strftime("%d/%m/%Y")
                # base_imp: 09.2
                content += "%012.2f" % line.withholding_id.base_amount
                tax = line._get_settlement_tax() or line.tax_line_id
                # alicuota: 09.6
                content += f"{tax.amount:0>16.6f}"
                # importe (req): 09.2
                content += "%012.2f" % abs(line.amount_currency)
                content += "\n"

        return [
            {
                "txt_filename": "DREI retenciones aplicadas.txt",
                "txt_content": content,
            }
        ]

    def misiones_files_values(self, move_lines):
        """Implementado segun especificación indicada en ticket 60295. También se puede ver detalles en readme"""
        self.ensure_one()
        content = ""
        for line in move_lines.sorted(key=lambda r: (r.date, r.id)):
            payment = line.payment_id
            tax = line._get_settlement_tax()
            alicuot = tax.amount
            if payment:
                # Fecha
                content += fields.Date.from_string(payment.date).strftime("%d-%m-%Y") + ","

                # Tipo de comprobante
                #    Aquí vemos si se está pagando al menos una nota de crédito
                #    si es así interpretamos que es corresponde a un CAR
                matched_move_types = payment.reconciled_bill_ids.mapped("move_type")
                is_car = False
                if "in_refund" in matched_move_types:
                    is_car = True
                    content += "CAR" + ","
                else:
                    content += "CR" + ","

                # Punto de Venta + Nro de Comprobante
                content += line.withholding_id.name.replace("-", "")[:20] + ","

                # Razón Social
                content += payment.partner_id.name.replace(",", "")[:100] + ","

                # CUIT
                payment.partner_id.ensure_vat()
                content += payment.partner_id.l10n_ar_formatted_vat + ","

                # Monto de operación
                content += "%.2f" % (abs(line.withholding_id.base_amount)) + ","

                # Alícuota
                content += str(alicuot) + ","

                if is_car:
                    # Tipo de comprobante original
                    content += "CR" + ","

                    # Comprobante que dio origen a la nota de crédito
                    # pago -> grupo de pagos --> nc --> factura --> grupo de pagos --> pago (con retenc misiones)
                    origin_invoice = payment.reconciled_bill_ids.reversed_entry_id
                    for pay in (
                        self.env["account.payment"]
                        .search(
                            [
                                ("partner_id", "=", origin_invoice.partner_id.id),
                                ("date", ">=", origin_invoice.invoice_date),
                            ]
                        )
                        .filtered(lambda x: origin_invoice in x.reconciled_bill_ids)
                    ):
                        retenciones_pago_fact_original = pay.l10n_ar_withholding_line_ids
                        cant_ret = 0
                        for withholding in retenciones_pago_fact_original:
                            line_withholding_tax = line.withholding_id._get_withholding_tax()
                            if withholding.tax_id == line_withholding_tax:
                                origin_withholding_cr = withholding
                                cant_ret += 1
                        if cant_ret != 1 or origin_withholding_cr.amount != line.withholding_id.amount:
                            raise ValidationError(
                                "Solo se admitirá un comprobante de anulación de retención referido a un solo comprobante de retención y la anulación debe ser por un importe igual al importe total de la retención original. Revisar pago/s %s. El pago que anula la retención es %s (id: %s)"
                                % (
                                    retenciones_pago_fact_original.payment_id.mapped("name"),
                                    line.payment_id.name,
                                    line.payment_id.id,
                                )
                            )

                        payment_date = line.date
                        origin_line_cr_date = origin_withholding_cr.payment_id.date
                        if (payment_date.year - origin_line_cr_date.year) * 12 + (
                            payment_date.month - origin_line_cr_date.month
                        ) > 2:
                            raise ValidationError(
                                "Solo se admitirá un comprobante de anulación de retención para un comprobante de origen dentro de los dos períodos anteriores. Revisar pago/s %s. El pago que anula la retención es %s (id: %s)".format()
                            )

                        if payment_date < origin_line_cr_date:
                            raise ValidationError(
                                "La fecha del comprobante de anulación de retención no puede ser anterior al de la retención que está anulando. Revisar pago/s %s. El pago que anula la retención es %s (id: %s)".format()
                            )

                        payment_partner_vat = line.partner_id.ensure_vat()
                        origin_payment_partner_vat = origin_withholding_cr.payment_id.partner_id.ensure_vat()
                        if payment_partner_vat != origin_payment_partner_vat:
                            raise ValidationError(
                                "Deben coincidir los CUIT emisores del comprobante de anulación de retención y del comprobante de retención original.  Revisar pago/s %s. El pago que anula la retención es %s (id: %s)".format()
                            )

                    # Nro de comprobante que dio origen a la nota de crédito
                    content += origin_withholding_cr.name.replace("-", "")[:20] + ","

                    # Fecha del comprobante que dio origen a la nota de crédito
                    content += origin_withholding_cr.payment_id.date.strftime("%d-%m-%Y") + ","

                    # CUIT del comprobante que dio origen a la nota de crédito
                    partner_vat = origin_withholding_cr.payment_id.partner_id.ensure_vat()
                    content += partner_vat
                else:
                    content += ",,,"

                content += "\n"
            elif line.move_id.is_invoice():
                # Fecha
                invoice_date = line.move_id.invoice_date
                content += invoice_date.strftime("%d-%m-%Y") + ","

                # Tipo de comprobante
                content += line.move_id.l10n_latam_document_type_id.doc_code_prefix.replace("-", "_") + ","

                # Número
                content += line.move_id.l10n_latam_document_number.replace("-", "")[:20] + ","

                # Nombre
                content += line.move_id.partner_id.name[:100] + ","

                # CUIT
                partner_vat = line.move_id.partner_id.ensure_vat()
                content += partner_vat + ","

                # Importe de la operación, consultar si l10n_latam_price_net es correcto
                content += str(line.tax_base_amount) + ","

                # Alícuota
                content += str(alicuot)

                if line.move_id.l10n_latam_document_type_id.doc_code_prefix[:3] == "NC-":
                    # Comprobante de origen
                    origin_invoice = line.move_id.reversed_entry_id

                    if not origin_invoice:
                        raise ValidationError(
                            "No puede generarse la descarga si en el archivo hay percepciones en notas de crédito y dichas notas de cŕedito no tienen indicado cuál es el comprobante original que se está revirtiendo (ejemplo: una factura). Revisar %s (id: %s)."
                            % (line.move_id.name, line.move_id.id)
                        )

                    # CUIT del partner del comprobante de origen
                    partner_vat_origin_invoice = origin_invoice.partner_id.ensure_vat()

                    # Fecha del comprobante original
                    date_origin_invoice = origin_invoice.invoice_date

                    if (invoice_date.year - date_origin_invoice.year) * 12 + (
                        invoice_date.month - date_origin_invoice.month
                    ) > 2:
                        raise ValidationError(
                            "Solo se admitirá una NC para un comprobante de origen dentro de los dos períodos anteriores, revisar %s (id: %s) asociado a la factura %s (id: %s)"
                            % (line.move_id.name, line.move_id.id, origin_invoice.name, origin_invoice.id)
                        )

                    if invoice_date < date_origin_invoice:
                        raise ValidationError(
                            "La fecha de la NC no podrá ser anterior a la fecha del comprobante de origen, revisar %s (id: %s) asociado a la factura %s (id: %s)"
                            % (line.move_id.name, line.move_id.id, origin_invoice.name, origin_invoice.id)
                        )

                    if partner_vat != partner_vat_origin_invoice:
                        raise ValidationError(
                            "Deben coincidir los CUIT emisores de la NC y del comprobante original, revisar: %s (id: %s) asociado a la factura %s (id: %s)"
                            % (line.move_id.name, line.move_id.id, origin_invoice.name, origin_invoice.id)
                        )

                    # Tipo de comprobante original
                    content += "," + origin_invoice.l10n_latam_document_type_id.doc_code_prefix.replace("-", "_") + ","

                    # Nro de comprobante original
                    content += origin_invoice.l10n_latam_document_number.replace("-", "")[:20] + ","

                    # Fecha de comprobante original
                    content += date_origin_invoice.strftime("%d-%m-%Y") + ","

                    # CUIT de comprobante original
                    content += partner_vat_origin_invoice
                else:
                    content += ",,,,"

                content += "\n"

        return [
            {
                "txt_filename": ("Retenciones " if payment else "Percepciones ") + "Misiones.txt",
                "txt_content": content,
            }
        ]

    def retenciones_iva_files_values(self, move_lines):
        """Implementado segun especificación indicada en ticket 54274."""
        self.ensure_one()
        content = ""
        for line in move_lines.sorted(key=lambda r: (r.date, r.id)):
            payment = line.payment_id
            if payment:
                # regimen (long 3)
                line_withholding_tax = line.withholding_id._get_withholding_tax()
                codigo_regimen = line_withholding_tax.l10n_ar_code
                if not codigo_regimen:
                    raise ValidationError(
                        _('No hay código de régimen en la configuración del impuesto "%s"')
                        % (line_withholding_tax.name)
                    )
                if len(codigo_regimen) < 3:
                    raise ValidationError(
                        _('El código de régimen tiene que tener 3 dígitos en la configuración del impuesto "%s"')
                        % (line_withholding_tax.name)
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
            elif line.move_id.is_invoice():
                tax = line._get_settlement_tax()
                # regimen (long 3)
                codigo_regimen = tax.l10n_ar_code
                if not codigo_regimen:
                    raise ValidationError(
                        _('No hay código de régimen en la configuración del impuesto "%s"') % (tax.name)
                    )
                if len(codigo_regimen) < 3:
                    raise ValidationError(
                        _('El código de régimen tiene que tener 3 dígitos en la configuración del impuesto "%s"')
                        % (tax.name)
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

        return [
            {
                "txt_filename": ("Retenciones" if payment else "Percepciones") + "_iva.txt",
                "txt_content": content,
            }
        ]

    def iibb_aplicado_arba_desde_01032026_files_values(self, move_lines):
        """Extendemos para que solo si esta disponible el módulo de arba_ws se incluya la generación del
        archivo para registrar reteciones por lote"""
        self.ensure_one()
        return self.iibb_aplicado_arba_desde_01032026(
            move_lines
        ) + self.iibb_alta_ret_aplicado_arba_por_lote_a122r_01032026(move_lines)

    def iibb_aplicado_arba_act_7_desde_01032026_files_values(self, move_lines):
        """Extendemos para que solo si esta disponible el módulo de arba_ws se incluya la generación del
        archivo para registrar reteciones por lote"""
        self.ensure_one()
        return self.iibb_aplicado_arba_desde_01032026(
            move_lines, act_7=True
        ) + self.iibb_alta_ret_aplicado_arba_por_lote_a122r_01032026(move_lines)

    def iibb_aplicado_arba_desde_01032026(self, move_lines, act_7=None):
        """Desarrollado según especificación https://web.arba.gov.ar/instructivo-y-marco-normativo
        (ese enlace se obtiene de https://web.arba.gov.ar/agentes#presentacion-de-ddjj ,
        luego hay que ir a la sección "DDJJ Periódicas Web IIBB NOVEDAD" y hacer click en
        "Instructivos y Marco Normativo - NOVEDAD -"). Finalmente descargar la especificación
        donde dice 'Descargar PDF (Nuevo Diseño - Vigente para operaciones a partir del 01/03/2026)'
        Implementados:
            - 1.2 Percepciones Act. 7 método Percibido (quincenal)
            - 1.7 Retenciones ( excepto actividad 29, 6 de Bancos y 17 de
            Bancos y No Bancos)
        """
        self.ensure_one()
        ret = ""
        perc = ""
        percepciones_monto_modificado = []

        for line in move_lines:
            # pay_group = payment.payment_group_id
            move = line.move_id
            payment = line.payment_id
            internal_type = line.l10n_latam_document_type_id.internal_type
            document_code = line.l10n_latam_document_type_id.code

            line.partner_id.ensure_vat()

            # CUIT contribuyente Percibido (long 13, desde 1 hasta 13. Formato 99-99999999-9)
            content = line.partner_id.l10n_ar_formatted_vat
            # Fecha Percepción (long 10, desde 14 hasta 23. Formato dd/mm/aaaa)
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # solo para percepciones
            if not payment:
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
            monto_imponible = False
            if payment:
                content += format_amount(line.withholding_id.base_amount, 14, 2, ",")
            else:
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
            if monto_imponible:
                # por ahora solo hacemos este cálculo para percepciones,
                # no lo hacemos para retenciones por ahora
                importe_percepcion_calculado = format_amount(monto_imponible * alicuota / 100, 13, 2, ",")
            # ARBA valida importe = base * alícuota; informar el importe calculado
            # cuando difiere del original por redondeos (calculado por odoo).
            if monto_imponible and importe_percepcion != importe_percepcion_calculado:
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
            if act_7 and not payment:
                # Fecha Emisión (long 10, desde 71 hasta 80)
                content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")
            # Tipo Operación (long 1, desde 71 hasta 71 o desde 81 a 81 si es act_7)
            # A= Alta, B=Baja, M=Modificación.
            content += "A"
            content += "\r\n"

            if payment:
                ret += content
            else:
                perc += content

        # para la fecha de la presentación tomamos la fecha de un apunte a liquidar
        # el valor de la quincena puede ser 0, 1, 2. deberiamos ver si podemos
        # completarlo de alguna manera
        period = move_lines and fields.Date.from_string(move_lines[0].date).strftime("%Y%mX") or ""

        # AR-CUIT-PERIODO-ACTIVIDAD-LOTE_MD5
        perc_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat,
            period,
            "7",  # 7 serian las percepciones
        )

        # AR-vat-PERIODO-ACTIVIDAD-LOTE_MD5
        ret_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat,
            period,
            "6",  # 6 serian las retenciones
        )

        if percepciones_monto_modificado:
            comprobantes_modificados = "\n".join(
                "%(id)s - %(nombre)s - %(importe_original)s - %(importe_calculado)s" % percepcion
                for percepcion in percepciones_monto_modificado
            )
            _logger.info(
                "Percepciones ARBA con importe ajustado:\nid - nombre - importe original - importe calculado\n%s",
                comprobantes_modificados,
            )

        return [
            {
                "txt_filename": perc_txt_filename,
                "txt_content": perc,
            },
            {
                "txt_filename": ret_txt_filename,
                "txt_content": ret,
            },
        ]

    def iibb_alta_ret_aplicado_arba_por_lote_a122r_01032026(self, move_lines):
        """Desarrollado según especificación Webservice (A122R):
        https://web.arba.gov.ar/Instructivos-y-Marco-Normativo-A-122R
        (ese enlace se obtiene de https://web.arba.gov.ar/agentes#presentacion-de-ddjj ,
        luego hay que ir a la sección "Comprobantes de Retención (A-122R) Nuevo" y
        hacer click en "Instructivo y Marco Normativo"). Finalmente descargar la especificación
        donde dice 'Descargar PDF'. En este método se desarrolla el punto 1
        'Retenciones (Régimen General y Regímenes Especiales)'
        Solo para retenciones. Vigente desde 01/03/2026."""
        self.ensure_one()
        content = ""

        # Forzamos para informar solo las retenciones (por las dudas por error seleccionen percepciones)
        move_lines = move_lines.filtered(lambda x: x.withholding_id)

        # Si el módulo de WS ARBA A122R está instalado, debemos filtrar para no informar en el TXT
        # las retenciones que ya fueron informadas via webservice.
        if self.env["ir.module.module"].search(
            [("name", "=", "l10n_ar_arba_ws"), ("state", "in", ["installed", "to upgrade"])]
        ):
            move_lines = move_lines.filtered(lambda x: not x.withholding_id.l10n_ar_cert_number)

        for line in move_lines:
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

        period = move_lines and fields.Date.from_string(move_lines[0].date).strftime("%Y%mX") or ""

        # ER-vat-PERIODO-ACTIVIDAD-LOTE_MD5
        # Esto funciona para el tipo de actividad 6 que es el regimen de retenciones generales.
        # En el futuro si agregamos mas regimenes/actividades debemos de sacar este dato
        # de la configuracion de la compañía
        filename = "ER-%s-%s-%s-LOTEXXXXX.txt" % (
            self.company_id.vat,
            period,
            "6",  # 6 serian las retenciones
        )

        return [
            {
                "txt_filename": filename,
                "txt_content": content,
            }
        ]
