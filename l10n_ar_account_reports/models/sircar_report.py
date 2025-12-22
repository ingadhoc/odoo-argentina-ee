# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import _, api, fields, models
from odoo.exceptions import RedirectWarning, UserError

from .helpers import format_amount, get_line_tax_base, get_standard_lines_domain


class L10n_ArSircarReportHandler(models.AbstractModel):
    _name = "l10n_ar.sircar.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian SIRCAR Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        txt_export_button = [
            {
                "name": "TXT Retenciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "sircar_ret_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
            {
                "name": "TXT Percepciones",
                "sequence": 30,
                "action": "export_file",
                "action_param": "sircar_perc_txt",
                "file_export_type": "TXT",
                "branch_allowed": True,
            },
        ]

        options["buttons"].extend(txt_export_button)

    def sircar_ret_txt(self, options):
        return {
            "file_name": "Retenciones IIBB SIRCAR Aplicadas.txt",
            "file_content": self._sircar_get_txt_files(options, file_type="ret"),
            "file_type": "txt",
        }

    def sircar_perc_txt(self, options):
        return {
            "file_name": "Percepciones IIBB SIRCAR Aplicadas.txt",
            "file_content": self._sircar_get_txt_files(options, file_type="perc"),
            "file_type": "txt",
        }

    def _sircar_get_txt_files(self, options, file_type):
        """Returns SIRCAR txt content"""
        move_lines = self._sircar_get_txt_lines(options, file_type)
        return "".join(self._get_sircar_txt_content(move_lines, file_type)).encode("ISO-8859-1", "ignore")

    def _sircar_get_txt_lines(self, options, file_type):
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        domain = [
            ("tax_line_id.l10n_ar_state_id.code", "not in", ["C", "B", "T"]),
            ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
        ] + get_standard_lines_domain(self.env.company.ids, options)

        if file_type == "ret":
            domain += [("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier")]
        elif file_type == "perc":
            domain += [("tax_line_id.type_tax_use", "=", "sale")]
        return self.env["account.move.line"].search(domain, order="date asc, name asc, id asc")

    def _get_sircar_txt_content(self, move_lines, file_type):
        """Returns the lines to be printed in the txt file.
        Especificacion en /doc/sircar, solicitado en ticket 62526
        """
        lines = []
        line_nbr = 1
        if file_type == "ret":
            for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
                tax = line._get_settlement_tax()
                alicuot = tax.amount

                internal_type = line.l10n_latam_document_type_id.internal_type

                # 1 Número de Renglón (único por archivo)
                content = []
                content.append("%05d" % line_nbr)

                # 2 Origen del Comprobante
                content.append("1")

                # 3 Tipo del Comprobante
                if line.payment_id.payment_type == "outbound":
                    content.append("1")
                else:
                    content.append("2")

                # 4 Número del comprobante
                content.append("%012d" % int(re.sub("[^0-9]", "", line.payment_id.name or "")))

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
                            "No hay regimen de retencion (ARCA Code 'l10n_ar_code') configurado para el impuesto '%(tax_name)s' del partner '%(partner_name)s'",
                            tax_name=tax.name,
                            partner_name=line.partner_id.name,
                        ),
                        action=tax.get_formview_action(),
                        button_text=_("Edit tax"),
                    )
                content.append(tax.l10n_ar_code)

                # 11 Jurisdicción: código en Convenio Multilateral de la
                # jurisdicción a la cual está presentando la DDJJ
                if not tax.l10n_ar_state_id.jurisdiction_code or not tax.l10n_ar_state_id.jurisdiction_code:
                    raise RedirectWarning(
                        message=_(
                            'No hay jurisdicción establecida en el impuesto "%(tax_name)s" o no tiene código de jurisdicción.',
                            tax_name=tax.name,
                        ),
                        action=tax.get_formview_action(),
                        button_text=_("Edit tax"),
                    )

                content.append(tax.l10n_ar_state_id.jurisdiction_code)

                # Tipo registro 2. Provincia Cordoba
                if tax.l10n_ar_state_id.jurisdiction_code in ["904", "914"]:
                    # 12 Tipo de Operación (1-Efectuada, 2-Anulada, 3-Omitida)
                    content.append("2" if internal_type == "supplier_payment" else "1")

                    # 13 Fecha de Emisión de Constancia (en formato dd/mm/aaaa)
                    content.append(fields.Date.from_string(line.date).strftime("%d/%m/%Y"))

                    # 14 Número de Constancia - Numeric(14)
                    content.append("%014s" % int(re.sub("[^0-9]", "", line.withholding_id.name or "0")[:14]))

                    # 15 Número de Constancia original (sólo para las Anulaciones –ver códigos por jur-)  - Numeric(14)
                    original_invoice = line.payment_id.reconciled_bill_ids.reversed_entry_id or line.move_id
                    content.append(
                        "%014d" % int(re.sub("[^0-9]", "", original_invoice.name or ""))
                        if internal_type == "supplier_payment"
                        else "%014d" % 0
                    )
                lines.append(",".join(content) + "\r\n")
                line_nbr += 1
        elif file_type == "perc":
            for line in move_lines.filtered("amount_currency").sorted(key=lambda r: (r.date, r.id)):
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
                    raise UserError(_("Tipo de comprobante no reconocido"))
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
                content.append(format_amount(abs(get_line_tax_base(line)), 12, 2, "."))

                # 8 alicuota de la percepcion
                content.append(format_amount(alicuot, 6, 2, "."))

                # 9 Monto percibido
                content.append(format_amount(abs(line.balance), 12, 2, "."))

                # 10 Tipo de Régimen de Percepción
                # (código correspondiente según tabla definida por la jurisdicción)
                if not tax.l10n_ar_code:
                    raise RedirectWarning(
                        message=_(
                            "No hay régimen de percepción (ARCA Code 'l10n_ar_code') configurado para el impuesto: '%(tax_name)s'.",
                            tax_name=tax.name,
                        ),
                        action=tax.get_formview_action(),
                        button_text=_("Edit tax"),
                    )
                content.append(tax.l10n_ar_code)

                # 11 Jurisdicción: código en Convenio Multilateral de la
                # jurisdicción a la cual está presentando la DDJJ
                if not tax.l10n_ar_state_id.jurisdiction_code or not tax.l10n_ar_state_id.jurisdiction_code:
                    raise RedirectWarning(
                        message=_(
                            'No hay jurisdicción establecida en el impuesto "%(tax_name)s" o no tiene código de jurisdicción.',
                            tax_name=tax.name,
                        ),
                        action=tax.get_formview_action(),
                        button_text=_("Edit tax"),
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

                lines.append(",".join(content) + "\r\n")
                line_nbr += 1

        return lines

    @api.model
    def _get_perception_original_invoice_number(self, line):
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
            raise UserError(_("Tipo de comprobante no reconocido"))
        res += str(document_type)[:1]

        # 3 Letra del comprobante
        res += letter

        # 4 Número del comprobante
        res += "%012d" % int(re.sub("[^0-9]", "", related_invoice.l10n_latam_document_number or ""))
        return res
