# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import _, fields, models
from odoo.exceptions import RedirectWarning, UserError

from .helpers import get_standard_lines_domain


class L10n_ArSicoreReportHandler(models.AbstractModel):
    _name = "l10n_ar.sicore.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian SICORE Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # SICORE es una única presentación: un solo TXT que combina las
        # retenciones de ganancias e IVA con las percepciones de IVA.
        txt_export_button = {
            "name": _("SICORE TXT"),
            "sequence": 30,
            "action": "export_file",
            "action_param": "sicore_book_export_files_to_txt",
            "file_export_type": "TXT",
            "branch_allowed": True,
        }

        options["buttons"].append(txt_export_button)

    # ==========================================================================
    # Helpers comunes a retenciones y percepciones
    # ==========================================================================

    def _sicore_tax_code(self, tax):
        """SICORE tax code (campo "Codigo de Impuesto", 4 dígitos).

        "0217" para ganancias (identificadas por el tipo de retención) y "0767"
        para IVA, que es el resto de lo que llega acá: las retenciones y
        percepciones de IVA se reconocen por el código de tributo ARCA "06" de su
        grupo de impuestos, no por el tipo de retención.
        """
        return "0217" if tax.l10n_ar_tax_type in ("earnings", "earnings_scale") else "0767"

    def _sicore_regime(self, tax, tax_code, is_withholding):
        """Devuelve (campo régimen [3], código de condición [2]) de un impuesto.

        Ganancias: régimen tal cual (o "000" si falta), condición "01".
        IVA: régimen del impuesto, con el 499 ("otros") como fallback solo en
        retenciones; condición "01" salvo régimen 602 (13/14 según la alícuota)
        o 214/493 ("00"), según las relaciones de códigos SICORE de
        doc/Sicore/relaciones-codigos-sicore.csv.
        """
        regimen_code = "".join(filter(str.isdigit, str(tax.l10n_ar_code or "")))[:3]
        if tax_code == "0217":
            return (f"{regimen_code:0>3}" if regimen_code else "000"), "01"
        if not regimen_code and is_withholding:
            # 499 es el régimen "otros" de las retenciones de IVA; en percepciones
            # no existe, así que el campo sale en cero.
            regimen_code = "499"
        regimen_field = f"{regimen_code:0>3}"
        codcond = "01"
        if regimen_code == "602":
            codcond = "13" if (tax.amount_type == "percent" and tax.amount == 3) else "14"
        elif regimen_code in ("214", "493"):
            codcond = "00"
        return regimen_field, codcond

    def _sicore_check_partner(self, partner):
        """Valida los datos del contacto que informa el registro SICORE.

        Cada aviso redirige al registro donde se corrige el dato faltante: el
        código ARCA está en el tipo de identificación y el CUIT en el contacto.
        """
        identification_type = partner.l10n_latam_identification_type_id
        if not identification_type.l10n_ar_afip_code:
            raise RedirectWarning(
                message=_(
                    'The identification type "%(identification_type)s" does not have ARCA code set.',
                    identification_type=identification_type.name,
                ),
                action=identification_type.get_formview_action(),
                button_text=_("Edit identification type"),
            )
        if not partner.vat:
            raise RedirectWarning(
                message=_(
                    'The partner "%(partner_name)s" (id %(partner_id)s) does not have the vat set.',
                    partner_name=partner.name,
                    partner_id=partner.id,
                ),
                action=partner.get_formview_action(),
                button_text=_("Edit contact"),
            )

    def _sicore_record_tail(self, partner, issue_date, amount):
        """Tramo final común del registro SICORE (idéntico en retenciones y
        percepciones): importe, porcentaje de exclusión, fecha de boletín,
        documento del sujeto y número de certificado."""
        content = ""
        # Retención Pract. a Suj. ..     [ 1]
        content += "0"
        # Importe de Retencion / Percepcion (amount)          [14]
        content += f"{abs(amount):014.2f}"
        # Porcentaje de Exclusion (exclusion percentage)       [ 6]
        content += "000.00"
        # Fecha Emision Boletin          [10] (dd/mm/yyyy)
        content += fields.Date.from_string(issue_date).strftime("%d/%m/%Y")
        # Tipo Documento Retenido (document type code)       [ 2]
        content += f"{int(partner.l10n_latam_identification_type_id.l10n_ar_afip_code):02d}"
        # Numero Documento Retenido (vat)     [20]
        # El campo espera el número sin separadores; el tipo va en el campo
        # anterior. No usamos ensure_vat() porque solo devuelve el CUIT, y acá
        # también hay que soportar DNI, CUIL y pasaporte.
        content += re.sub(r"\D", "", partner.vat or "").ljust(20)
        # Numero Certificado Original    [14]
        content += f"{0:014d}"
        content += "\r\n"
        return content

    # ==========================================================================
    # Export (una sola presentación SICORE)
    # ==========================================================================

    def sicore_book_export_files_to_txt(self, options):
        """Export method that lets us export the SICORE book to a txt file.
        It contains the file that we upload to SICORE application."""
        return {
            "file_name": _("SICORE Aplicado.txt"),
            "file_content": self._sicore_book_get_txt_files(options),
            "file_type": "txt",
        }

    def _sicore_book_get_txt_files(self, options):
        """Returns SICORE txt content.

        SICORE es una única presentación: el TXT combina las retenciones de
        ganancias e IVA con las percepciones de IVA en un solo archivo, con
        todos los registros ordenados por fecha de emisión.
        """
        state = options.get("all_entries") and "all" or "posted"
        if state != "posted":
            raise UserError(
                _(
                    "Can only generate TXT files using posted entries."
                    " Please remove Include unposted entries filter and try again"
                )
            )
        # Cada builder devuelve tuplas (fecha, contenido) para poder intercalar
        # retenciones y percepciones en un único archivo ordenado por fecha.
        records = self._get_sicore_withholding_content(self._sicore_get_withholding_lines(options))
        records += self._get_sicore_perception_content(self._sicore_get_perception_lines(options))
        records.sort(key=lambda record: (record[0], record[1]))
        return "".join(content for *_key, content in records).encode("ISO-8859-1", "ignore")

    # ==========================================================================
    # Retenciones (ganancias + IVA) — datos tomados del pago
    # ==========================================================================

    def _sicore_get_withholding_lines(self, options):
        # Retenciones nacionales sobre pagos a proveedores (sin jurisdicción,
        # que excluye IIBB). Cada tipo se identifica con lo que hay disponible en
        # el impuesto:
        # - Ganancias: tipo de retención earnings / earnings_scale.
        # - IVA: código de tributo ARCA "06" en el grupo de impuestos. El tipo de
        #   retención no sirve acá porque su selection no tiene opción de IVA.
        # Restringimos a apuntes con pago para no procesar asientos manuales,
        # de los que no podemos sacar ni el comprobante ni la base de cálculo.
        domain = [
            ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ("tax_line_id.country_code", "=", "AR"),
            ("tax_line_id.l10n_ar_state_id", "=", False),
            "|",
            ("tax_line_id.l10n_ar_tax_type", "in", ["earnings", "earnings_scale"]),
            ("tax_line_id.l10n_ar_tribute_afip_code", "=", "06"),
        ] + get_standard_lines_domain(self.env["account.report"].get_report_company_ids(options), options)
        return self.env["account.move.line"].search(domain, order="date asc, id asc")

    def _get_sicore_withholding_content(self, move_lines):
        """Returns (date, line id, content) tuples for the withholding lines (retenciones)."""
        lines = []
        # Filtramos por balance, que es el importe que informa el registro y el
        # que suman las líneas del reporte, para que el TXT y los totales del
        for line in move_lines.filtered("balance"):
            content = ""

            partner = line.partner_id
            self._sicore_check_partner(partner)
            # Sin el registro de retención no tenemos de dónde sacar la base de
            # cálculo, y el registro saldría con la base en cero sin que nadie
            # se entere: el archivo queda bien formado y con un dato falso.
            if not line.withholding_id:
                raise RedirectWarning(
                    message=_(
                        'The payment "%(payment_name)s" (id %(payment_id)s) has a withholding tax that is not'
                        " linked to a withholding, so its base amount cannot be reported.",
                        payment_name=line.payment_id.display_name,
                        payment_id=line.payment_id.id,
                    ),
                    action=line.payment_id.get_formview_action(),
                    button_text=_("View payment"),
                )

            payment = line.payment_id
            move = line.move_id
            tax = line._get_settlement_tax(date=line.date)
            tax_code = self._sicore_tax_code(tax)
            regimen_field, codcond = self._sicore_regime(tax, tax_code, is_withholding=True)
            # payment.date es la fecha de emisión que informa el layout.
            issue_date = payment.date

            # Codigo del Comprobante (document code)        [ 2]
            content += (
                (payment.payment_type == "inbound" and "02") or (payment.payment_type == "outbound" and "06") or "00"
            )
            # Fecha Emision Comprobante (move line date)     [10] (dd/mm/yyyy)
            content += fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # Numero Comprobante (document number)           [16]
            content += f"{re.sub(r'[^0-9]', '', move.l10n_latam_document_number):0>16}"

            # Importe Comprobante (document amount)           [16]
            content += f"{abs(payment.payment_total):016.2f}"

            # Codigo de Impuesto (tax code)            [ 4]
            content += tax_code
            # Codigo de Regimen (regime code)             [ 3]
            content += regimen_field

            # Codigo de Operacion (operation code)           [ 1] -> 1 retención
            content += "1"

            # Base de Calculo (base amount)               [14]
            content += f"{abs(line.withholding_id.base_amount):014.2f}"

            # Fecha Emision Retencion (payment date)          [10] (dd/mm/yyyy)
            content += fields.Date.from_string(issue_date).strftime("%d/%m/%Y")

            # Codigo de Condicion (condition code)           [ 2]
            content += codcond

            # Tramo final común del registro.
            content += self._sicore_record_tail(partner, issue_date, line.balance)

            # La clave de orden es la fecha de emisión de la retención (issue_date =
            # payment.date), que es la que se informa en el layout, más el id del
            # apunte para desempatar dentro de la misma fecha.
            lines.append((issue_date, line.id, content))
        return lines

    # ==========================================================================
    # Percepciones de IVA — datos tomados del comprobante
    # ==========================================================================

    def _sicore_get_perception_lines(self, options):
        # Percepciones de IVA aplicadas en ventas: impuestos de venta, sin
        # jurisdicción, cuyo grupo tiene código de tributo ARCA "06".
        # Las percepciones de ganancias no se informan en esta presentación.
        # Restringimos a comprobantes de venta (facturas/NC/ND) para no procesar
        # asientos manuales sin fecha ni número de comprobante.
        domain = [
            ("tax_line_id.type_tax_use", "=", "sale"),
            ("tax_line_id.l10n_ar_state_id", "=", False),
            ("tax_line_id.l10n_ar_tribute_afip_code", "=", "06"),
            ("tax_line_id.country_code", "=", "AR"),
        ] + get_standard_lines_domain(self.env["account.report"].get_report_company_ids(options), options)
        return self.env["account.move.line"].search(domain, order="date asc, id asc")

    def _get_sicore_perception_content(self, move_lines):
        """Returns (date, line id, content) tuples for the perception lines (percepciones)."""
        lines = []
        for line in move_lines.filtered("balance"):
            content = ""
            partner = line.partner_id
            self._sicore_check_partner(partner)

            move = line.move_id
            internal_type = move.l10n_latam_document_type_id.internal_type
            is_credit_note = internal_type == "credit_note"

            issue_date = move.invoice_date
            tax = line._get_settlement_tax(date=issue_date)
            # Solo informamos percepciones de IVA en esta presentación.
            tax_code = "0767"
            regimen_field, codcond = self._sicore_regime(tax, tax_code, is_withholding=False)

            # Codigo del Comprobante (document code)        [ 2]
            content += {"invoice": "01", "credit_note": "03", "debit_note": "04"}.get(internal_type, "05")

            # Fecha Emision Comprobante (invoice date)      [10] (dd/mm/yyyy)
            content += fields.Date.from_string(issue_date).strftime("%d/%m/%Y")

            # Numero Comprobante (document number)          [16] (5 punto de venta + 11 número)
            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number, move.l10n_latam_document_type_id.code
            )
            content += "{:0>5d}".format(document_parts["point_of_sale"])
            content += "{:0>11d}".format(document_parts["invoice_number"])

            # Importe Comprobante (document amount)         [16]
            content += f"{abs(move.amount_total_signed):016.2f}"

            # Codigo de Impuesto (tax code)                 [ 4]
            content += tax_code
            # Codigo de Regimen (regime code)               [ 3]
            content += regimen_field

            # Codigo de Operacion (operation code)          [ 1] -> 2 percepción
            content += "2"

            # Base de Calculo (base amount)                 [14]
            # En notas de crédito informamos el importe de la percepción como base
            # para resolver la inconsistencia detectada en el ticket 61671.
            base_amount = line.balance if is_credit_note else line.tax_base_amount
            content += f"{abs(base_amount):014.2f}"

            # Fecha Emision Retencion (invoice date)        [10] (dd/mm/yyyy)
            content += fields.Date.from_string(issue_date).strftime("%d/%m/%Y")

            # Codigo de Condicion (condition code)          [ 2]
            content += codcond

            # Tramo final común del registro.
            content += self._sicore_record_tail(partner, issue_date, line.balance)

            lines.append((issue_date, line.id, content))
        return lines
