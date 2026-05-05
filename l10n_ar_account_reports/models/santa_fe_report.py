# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import _, fields, models
from odoo.exceptions import RedirectWarning, UserError

from .helpers import get_pos_and_number, get_standard_lines_domain


class L10n_ArSantaFeReportHandler(models.AbstractModel):
    _name = "l10n_ar.santa_fe.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian Santa Fe Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones / Percepciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "santa_fe_ret_perc_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
        ]
        options["buttons"].extend(txt_export_button)

    def santa_fe_ret_perc_txt(self, options):
        return {
            "file_name": "Perc/Ret IIBB Santa Fe Aplicadas.txt",
            "file_content": self._santa_fe_get_txt_files(options),
            "file_type": "txt",
        }

    def _santa_fe_get_txt_files(self, options):
        """Returns Santa Fe txt content"""
        move_lines = self._santa_fe_get_txt_lines(options)
        return "".join(self._get_santa_fe_txt_content(move_lines)).encode("ISO-8859-1", "ignore")

    def _santa_fe_get_txt_lines(self, options):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "=", "S"),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
            "|",
            ("tax_line_id.type_tax_use", "=", "sale"),
            ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
        ] + get_standard_lines_domain(self.env.company.ids, options)
        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _get_santa_fe_txt_content(self, move_lines):
        """Returns the lines to be printed in the txt file."""
        lines = []

        def format_amount(amount, integers, decimals=2):
            # overwrite default format_amount
            template = "%0" + "%ss" % (integers + decimals + 1)
            # TODO se podria mejorar haciendo algo asi pero hace falta
            # hacer parametro el 16
            # "{0:>16.2f}".format(12.1)
            return template % f"{round(amount, decimals):.2f}".replace(".", ",")

        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""

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
                raise UserError(_("Tipo de impuesto %s equivocado") % (tax.tax_group_id.name))

            if not articulo_inciso_calculo or not articulo_inciso_retiene:
                raise RedirectWarning(
                    message=_(
                        'Debe establecer la información de "artículo/inciso" en la configuración del impuesto "%(tax_name)s"'
                        'en la solapa "API".',
                        tax_name=tax.name,
                    ),
                    action=tax.get_formview_action(),
                    button_text=_("Edit tax"),
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
                format_amount(abs(line.move_id.amount_total_signed), 11, 2)
                if line.move_id.is_invoice()
                else format_amount(abs(-line.balance), 11, 2)
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
                raise RedirectWarning(
                    message=_(
                        'Debe establecer el tipo de inscripción de IIBB del partner "%(partner_name)s" (id: %(partner_id)s)',
                        partner_name=partner.name,
                        partner_id=partner.id,
                    ),
                    action=partner.get_formview_action(),
                    button_text=_("Editar contacto"),
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
                raise UserError(
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
            #     raise UserError(_(
            #         'Debe seleccionar situación DREI para partner '
            #         '"%s" (id: %s)') % (
            #             partner.name, partner.id))
            content += partner.drei == "activo" and "1" or "0"

            # 16 - Importe Otros Gravámenes
            # TODO implementar
            content += format_amount(0.0, 9, 2)

            # 17 - Importe IVA (solo si factura)
            if line.move_id.is_invoice():
                base_lines, _tax_lines = line.move_id._get_rounded_base_and_tax_lines()
                amounts = line.move_id._l10n_ar_get_amounts(base_lines=base_lines)
                vat_amount = amounts["vat_amount"]
                base_amount = amounts["vat_taxable_amount"]
            else:
                vat_amount = 0.0
                base_amount = line.payment_id and line.withholding_id.base_amount or 0.0
            content += format_amount(vat_amount, 9, 2)

            # 18 - Base Imponible para el cálculo
            # tal vez la base deberiamos calcularlo asi, en pagos no porque
            # los asientos estan separados
            # content += format_amount(-get_line_tax_base(line), 12, 2, ',')
            content += format_amount(base_amount, 11, 2)

            # 19 - Alícuota / alicuota
            content += format_amount(tax.amount, 2, 2)

            # 20 - Impuesto Determinado
            content += format_amount(abs(-line.balance), 11, 2)

            # 21 - Derecho Registro e Inspección
            # TODO implementar
            # es un importe seguramente importe retenido de drei
            content += format_amount(0.0, 9, 2)

            # 22 - Monto Retenido
            # TODO por ahora es igual a impuesto determinado pero, podria ser
            # distinto en algún caso?
            content += format_amount(abs(-line.balance), 11, 2)

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

            lines.append(content)
        return lines
