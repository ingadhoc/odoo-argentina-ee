# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import _, fields, models
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools.float_utils import float_round

from .helpers import format_amount, get_standard_lines_domain


class L10n_ArCabaReportHandler(models.AbstractModel):
    _name = "l10n_ar.caba.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian CABA Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones / Percepciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "caba_ret_perc_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT NC Perc/Ret Aplicadas",
                "sequence": 30,
                "action": "export_file",
                "action_param": "nc_caba_ret_perc_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
        ]

        options["buttons"].extend(txt_export_button)

    def caba_ret_perc_txt(self, options):
        return {
            "file_name": "Perc/Ret IIBB CABA Aplicadas.txt",
            "file_content": self._caba_get_txt_files(options),
            "file_type": "txt",
        }

    def nc_caba_ret_perc_txt(self, options):
        return {
            "file_name": "NC Perc/Ret IIBB CABA Aplicadas.txt",
            "file_content": self._caba_get_txt_files(options, refund=True),
            "file_type": "txt",
        }

    def _caba_get_txt_files(self, options, refund=False):
        """Returns CABA txt content"""
        move_lines = self._caba_get_txt_lines(options, refund=refund)
        return "".join(self._get_caba_txt_content(move_lines)).encode("ISO-8859-1", "ignore")

    def _caba_get_txt_lines(self, options, refund=False):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "=", "C"),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
            "|",
            ("tax_line_id.type_tax_use", "=", "sale"),
            ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
        ] + self._caba_get_lines_domain(options, refund)
        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _caba_get_lines_domain(self, options, refund=False):
        domain = get_standard_lines_domain(self.env.company.ids, options)
        if refund:
            domain += [("move_id.move_type", "=", "out_refund")]
        else:
            domain += [("move_id.move_type", "!=", "out_refund")]
        return domain

    def _get_caba_txt_content(self, move_lines):
        """Returns the lines to be printed in the txt file."""
        lines = []
        for line in move_lines.filtered("amount_currency").sorted("date"):
            content = ""

            company_currency = self.env.company.currency_id
            backward_comp_is_installed = self.env["ir.module.module"].search(
                [
                    ("name", "=", "l10n_ar_account_reports_backward_comp"),
                    ("state", "=", "installed"),
                ]
            )
            # pay_group = payment.payment_group_id
            payment = line.payment_id
            # implementamos esto que teniamos en agip para obtener alicuota de rectificativa
            date = line.move_id._found_related_invoice().date or line.date
            tax = line._get_settlement_tax(date=date)
            partner = line.partner_id
            internal_type = line.l10n_latam_document_type_id.internal_type

            if not partner.vat:
                raise RedirectWarning(
                    message=_(
                        'El partner "%(partner_name)s" (id %(partner_id)s) no tiene número de identificación establecido',
                        partner_name=partner.name,
                        partner_id=partner.id,
                    ),
                    action=partner.get_formview_action(),
                    button_text=_("Editar contacto"),
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
                content = self._complete_credit_note_content(line, content, alicuot)
            else:
                # 2 - Código de Norma (long 3, desde 2 hasta 4)
                # por ahora solo padron regimenes generales
                content += "029"

                # 3 - Fecha de retención/percepción (long 10, desde 5 hasta 14, formato dd/mm/aaaa)
                content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

                # 4 - Tipo de comprobante origen de la retención (long 2)
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

                # 5 - Letra del Comprobante (long 1)
                # segun vemos en los archivos de ejemplo solo en percepciones
                if payment:
                    content += " "
                else:
                    content += line.l10n_latam_document_type_id.l10n_ar_letter if internal_type == "invoice" else " "

                # 6 - Nro de comprobante (long 16)
                content += "%016d" % int(
                    re.sub("[^0-9]", "", re.sub(r"\s\(\d+\)$", "", line.move_id.l10n_latam_document_number or ""))
                )

                # 7 - Fecha del comprobante
                content += fields.Date.from_string(line.move_id.date).strftime("%d/%m/%Y")

                # obtenemos montos de los comprobantes
                if payment:
                    vat_amount = 0.0
                    total_amount, other_taxes_amount, taxable_amount = self._complete_payment_content(
                        line, alicuot, backward_comp_is_installed, payment, company_currency
                    )
                elif line.move_id.is_invoice():
                    base_lines, _tax_lines = line.move_id._get_rounded_base_and_tax_lines()
                    amounts = line.move_id._l10n_ar_get_amounts(base_lines=base_lines)
                    # segun especificacion el iva solo se reporta para estos
                    if line.l10n_latam_document_type_id.l10n_ar_letter in ["A", "M"]:
                        vat_amount = amounts["vat_amount"]
                    else:
                        vat_amount = 0.0

                    total_amount = (1 if line.move_id.is_inbound() else -1) * line.move_id.amount_total_signed

                    # por si se olvidaron de poner agip en una linea de factura
                    # la base la sacamos desde las lineas de impuesto
                    # taxable_amount = line.move_id.cc_amount_untaxed
                    # TODO: le tuve que agregar abs(), investigar si está bien que en facturas
                    # de cliente line.tax_base_amount da negativo y por qué da positivo en nc
                    # En 18 no hace falta agregarle abs()
                    taxable_amount = abs(line.tax_base_amount)

                    # tambien lo sacamos por diferencia para no tener error (por el
                    # calculo trucado de taxable_amount por ejemplo) y
                    # ademas porque el iva solo se reporta si es factura A, M
                    other_taxes_amount = company_currency.round(total_amount - taxable_amount - vat_amount)
                    # other_taxes_amount = line.move_id.cc_other_taxes_amount
                else:
                    raise UserError(_("El impuesto no está asociado"))

                # 8 - Monto del comprobante
                content += format_amount(total_amount, 16, 2, ",")

                # 9 - Nro de certificado propio
                content += (line.withholding_id.name or "").rjust(16, " ")

                # 10 - Tipo de documento del Retenido
                # vat
                if partner.l10n_latam_identification_type_id.name not in [
                    "CUIT",
                    "CUIL",
                    "CDI",
                ]:
                    raise RedirectWarning(
                        message=_(
                            'El contacto "%(partner_name)s" (id %(partner_id)s), debe tener el tipo de identificación'
                            " CUIT, CUIL, CDI.",
                            partner_name=partner.name,
                            partner_id=partner.id,
                        ),
                        action=partner.get_formview_action(),
                        button_text=_("Editar contacto"),
                    )
                doc_type_mapping = {"CUIT": "3", "CUIL": "2", "CDI": "1"}
                content += doc_type_mapping[partner.l10n_latam_identification_type_id.name]

                # 11 - Nro de documento del Retenido
                content += str(partner._get_id_number_sanitize())

                # 12 - Situación IB del Retenido
                # 1: Local 2: Convenio Multilateral
                # 4: No inscripto 5: Reg.Simplificado
                if not partner.l10n_ar_gross_income_type:
                    raise RedirectWarning(
                        message=self.env._(
                            'Debe setear el tipo de inscripción de IIBB del contacto "%(partner_name)s" (id: %(partner_id)s)',
                            partner_name=partner.name,
                            partner_id=partner.id,
                        ),
                        action=partner.get_formview_action(),
                        button_text=self.env._("Editar contacto"),
                    )

                # ahora se reportaria para cualquier inscripto el numero de cuit
                gross_income_mapping = {
                    "local": "5",
                    "multilateral": "2",
                    "exempt": "4",
                }
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
                    raise UserError(
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
                content += format_amount(
                    (-line.balance if not ret_perc_applied else ret_perc_applied),
                    16,
                    2,
                    ",",
                )

                # 21 - Monto Total Retenido/Percibido
                content += format_amount(
                    (-line.balance if not ret_perc_applied else ret_perc_applied),
                    16,
                    2,
                    ",",
                )

                # # 22 - Aceptacion
                content += " "

                # 24 - Fecha Aceptación "Expresa"
                content += "          "
                content += "\r\n"

            lines.append(content)
        return lines

    def _complete_credit_note_content(self, line, content, alicuot):
        ret_perc_applied = False
        # 2 - Nro. Nota de crédito
        content += "%012d" % int(re.sub("[^0-9]", "", line.move_id.l10n_latam_document_number or ""))
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
            raise UserError(
                _(
                    "No pudimos encontrar el comprobante original para %s "
                    '(id %s). Verifique que en la nota de crédito "%s", el'
                    " campo origen es el número de la factura original"
                )
                % (
                    line.move_id.display_name,
                    line.move_id.id,
                    line.move_id.display_name,
                )
            )
        # 6 - Tipo de comprobante origen de la retención
        # Identificamos si el comprobante de origen es una Factura de credito MiPyMEs sino lo
        # tratamos como una factura normal
        # NOTA: Esto solo aplica para el calculo de Percepciones
        content += "10" if or_inv.l10n_latam_document_type_id.code in ["201", "206", "211"] else "01"
        # 7 - Letra del Comprobante
        if line.payment_id:
            content += " "
        else:
            content += or_inv.l10n_latam_document_type_id.l10n_ar_letter
        # 8 - Nro de comprobante (original)
        content += "%016d" % int(re.sub("[^0-9]", "", or_inv.l10n_latam_document_number or ""))
        # 9 - Nro de documento del Retenido
        content += str(line.partner_id._get_id_number_sanitize())
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
        content += format_amount(
            (line.balance if not ret_perc_applied else ret_perc_applied),
            16,
            2,
            ",",
        )
        # 13 - Alícuota
        content += format_amount(alicuot, 5, 2, ",")
        content += "\r\n"
        return content

    def _complete_payment_content(self, line, alicuot, backward_comp_is_installed, payment, company_currency):
        # solo en comprobantes A, M segun especificacion
        total_amount = float_round(
            payment.move_id.amount_total_in_currency_signed,
            precision_digits=2,
        )
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
                    sum(related_payments.mapped("move_id.amount_total_in_currency_signed")),
                    precision_digits=2,
                )
        # es lo mismo que payment_group.matched_amount_untaxed
        taxable_amount = float_round(line.withholding_id.base_amount, precision_digits=2)

        # lo sacamos por diferencia
        return total_amount, company_currency.round(total_amount - taxable_amount), taxable_amount
