# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

from .helpers import format_amount, get_pos_and_number, get_standard_lines_domain


class L10n_ArSifereReportHandler(models.AbstractModel):
    _name = "l10n_ar.sifere.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian SIFERE Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones sufridas",
                "sequence": 30,
                "action": "export_file",
                "action_param": "sifere_ret_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT Percepciones sufridas",
                "sequence": 30,
                "action": "export_file",
                "action_param": "sifere_perc_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "Despachos de importación (no importar)",
                "sequence": 30,
                "action": "export_file",
                "action_param": "sifere_despachos_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
        ]
        options["buttons"].extend(txt_export_button)

    def sifere_ret_txt(self, options):
        return {
            "file_name": "Retenciones Sufridas SIFERE.txt",
            "file_content": self._sifere_get_txt_files(options, "ret"),
            "file_type": "txt",
        }

    def sifere_perc_txt(self, options):
        return {
            "file_name": "Percepciones Sufridas SIFERE.txt",
            "file_content": self._sifere_get_txt_files(options, "perc"),
            "file_type": "txt",
        }

    def sifere_despachos_txt(self, options):
        return {
            "file_name": "Despachos de importación (no importar).txt",
            "file_content": self._sifere_get_txt_files(options, "despachos"),
            "file_type": "txt",
        }

    def _sifere_get_txt_files(self, options, file_type):
        """Returns SIFERE txt content"""
        move_lines = self._sifere_get_txt_lines(options, file_type)
        return "".join(self._get_sifere_txt_content(move_lines, file_type)).encode("ISO-8859-1", "ignore")

    def _sifere_get_txt_lines(self, options, file_type):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
        ] + get_standard_lines_domain(self.env.company.ids, options)

        if file_type == "ret":
            domain += [("tax_line_id.l10n_ar_withholding_payment_type", "=", "customer")]
        elif file_type == "perc":
            domain += [
                ("tax_line_id.type_tax_use", "=", "purchase"),
                ("l10n_latam_document_type_id.code", "not in", ["66", "67"]),
            ]
        elif file_type == "despachos":
            domain += [("l10n_latam_document_type_id.code", "in", ["66", "67"])]
        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _get_sifere_txt_content(self, move_lines, file_type):
        """Returns the lines to be printed in the txt file.
        Especificación según:
        https://drive.google.com/file/d/0B3trzV0e2WzvUjB1MnhXT0VteFE/view

        tal vez querramos agregar chequeo de que es "sifere" viendo que es
        cia multilateral

        * para consultas directo a sifere mesa de ayuda enviar correo electronico a
        sifereweb@comisionarbitral.gob.ar
        """
        lines = []
        desp_imp = []
        for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
            content = ""

            if file_type == "despachos":
                desp_imp.append(" - " + line.move_id.display_name + "\n")
                continue
            move = line.move_id
            internal_type = line.l10n_latam_document_type_id.internal_type

            if not line.partner_id:
                raise UserError(
                    _('La percepción %s (id: %d) del comprobante "%s" (id: %d) no tiene contacto asociado.')
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
            if file_type == "ret":
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
            if file_type == "ret":
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
            if file_type == "ret":
                content += "%020d" % int(re.sub("[^0-9]", "", move.l10n_latam_document_number))
            content += format_amount(line.balance, 11, 2, ",")
            content += "\r\n"

            lines.append(content)
        if desp_imp:
            desp_imp.insert(
                0,
                "En los registros seleccionados encontramos algunos despachos de importación, los mismos deben"
                "cargarse a mano. Los registros despachos corrspondientes son:\n",
            )
            return desp_imp

        return lines
