# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError

from .helpers import get_standard_lines_domain


class L10n_ArMisionesReportHandler(models.AbstractModel):
    _name = "l10n_ar.misiones.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian Misiones Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "misiones_ret_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT Percepciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "misiones_perc_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
        ]
        options["buttons"].extend(txt_export_button)

    def misiones_ret_txt(self, options):
        return {
            "file_name": "Retenciones IIBB Misiones.txt",
            "file_content": self._misiones_get_txt_files(options, "ret"),
            "file_type": "txt",
        }

    def misiones_perc_txt(self, options):
        return {
            "file_name": "Percepciones Misiones.txt",
            "file_content": self._misiones_get_txt_files(options, "perc"),
            "file_type": "txt",
        }

    def _misiones_get_txt_files(self, options, file_type):
        """Returns Misiones txt content"""
        move_lines = self._misiones_get_txt_lines(options, file_type)
        return "".join(self._get_misiones_txt_content(move_lines, file_type)).encode("ISO-8859-1", "ignore")

    def _misiones_get_txt_lines(self, options, file_type):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "=", "N"),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
        ] + get_standard_lines_domain(self.env.company.ids, options)

        if file_type == "ret":
            domain += [("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier")]
        elif file_type == "perc":
            domain += [("tax_line_id.type_tax_use", "=", "sale")]

        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _get_misiones_txt_content(self, move_lines, file_type):
        """Returns the lines to be printed in the txt file.
        Implementado segun especificación indicada en ticket 60295. También se puede ver detalles en readme
        """
        lines = []
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""
            payment = line.payment_id
            tax = line._get_settlement_tax()
            alicuot = tax.amount
            if file_type == "ret":
                # Fecha
                content += fields.Date.from_string(payment.date).strftime("%d-%m-%Y") + ","

                # Tipo de comprobante
                # Aquí vemos si se está pagando al menos una nota de crédito
                # si es así interpretamos que es corresponde a un CAR
                is_car = False
                if payment.reconciled_bill_ids.filtered(lambda x: x.move_type == "in_refund"):
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
                    # Se buscan aquellos pagos donde se está pagando la origin_invoice
                    origin_invoice_withholdings = origin_invoice.reconciled_payment_ids.mapped(
                        "l10n_ar_withholding_line_ids"
                    )
                    origin_invoice_misiones_withholdings = origin_invoice_withholdings.filtered(
                        lambda x: x.tax_id == line.withholding_id._get_withholding_tax()
                    )
                    if not origin_invoice_misiones_withholdings:
                        raise UserError(
                            "No puede puede saberse que retención está revitiendo. Revisar pago '%s (id: %s).'"
                            % (line.payment_id.name, line.payment_id.id)
                        )
                    if len(origin_invoice_misiones_withholdings) > 1:
                        raise UserError(
                            "Solo se admitirá un comprobante de anulación de retención referido a un solo comprobante de retención. Revisar pago '%s (id: %s).'"
                            % (line.payment_id.name, line.payment_id.id)
                        )
                    if origin_invoice_misiones_withholdings.amount != line.withholding_id.amount:
                        raise UserError(
                            "La anulación debe ser por un importe igual al importe total de la retención original. Revisar pago '%s (id: %s).'"
                            % (line.payment_id.name, line.payment_id.id)
                        )

                    # Nro de comprobante que dio origen a la nota de crédito
                    content += origin_invoice_misiones_withholdings.name.replace("-", "")[:20] + ","

                    # Fecha del comprobante que dio origen a la nota de crédito
                    content += origin_invoice_misiones_withholdings.payment_id.date.strftime("%d-%m-%Y") + ","

                    # CUIT del comprobante que dio origen a la nota de crédito
                    partner_vat = origin_invoice_misiones_withholdings.payment_id.partner_id.ensure_vat()
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
                # TODO: le tuve que agregar abs(), investigar si está bien que en facturas
                # de cliente line.tax_base_amount da negativo y por qué da positivo en nc
                # En 18 no hace falta agregarle abs()
                content += str(abs(line.tax_base_amount)) + ","

                # Alícuota
                content += str(alicuot)
                if line.move_id.move_type == "out_refund":
                    # Comprobante de origen
                    origin_invoice = line.move_id.reversed_entry_id

                    if not origin_invoice:
                        raise UserError(
                            "No puede generarse la descarga si en el archivo hay percepciones en notas de crédito y dichas notas de cŕedito no tienen indicado cuál es el comprobante original que se está revirtiendo (ejemplo: una factura). Revisar '%s (id: %s).'"
                            % (line.move_id.name, line.move_id.id)
                        )

                    # CUIT del partner del comprobante de origen
                    partner_vat_origin_invoice = origin_invoice.partner_id.ensure_vat()

                    # Fecha del comprobante original
                    date_origin_invoice = origin_invoice.invoice_date

                    if (invoice_date.year - date_origin_invoice.year) * 12 + (
                        invoice_date.month - date_origin_invoice.month
                    ) > 2:
                        raise UserError(
                            "Solo se admitirá una NC para un comprobante de origen dentro de los dos períodos anteriores, revisar %s (id: %s) asociado a la factura %s (id: %s)"
                            % (line.move_id.name, line.move_id.id, origin_invoice.name, origin_invoice.id)
                        )

                    if invoice_date < date_origin_invoice:
                        raise UserError(
                            "La fecha de la NC no podrá ser anterior a la fecha del comprobante de origen, revisar %s (id: %s) asociado a la factura %s (id: %s)"
                            % (line.move_id.name, line.move_id.id, origin_invoice.name, origin_invoice.id)
                        )

                    if partner_vat != partner_vat_origin_invoice:
                        raise UserError(
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

            lines.append(content)
        return lines
