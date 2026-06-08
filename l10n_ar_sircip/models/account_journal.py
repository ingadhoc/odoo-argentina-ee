##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging

from odoo import _, fields, models
from odoo.addons.l10n_ar_account_tax_settlement.models.account_journal import (
    get_line_tax_base,
    get_pos_and_number,
)
from odoo.exceptions import RedirectWarning, ValidationError

_logger = logging.getLogger(__name__)

# Mapping tipo de comprobante Odoo → código SIRCIP DDJJ
# Fuente: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf campo 8
_TIPO_COMPROBANTE_SIRCIP = {
    "invoice": 1,  # Factura
    "debit_note": 2,  # Nota de Débito
    "credit_note": 102,  # Nota de Crédito
}

# Tipo de Registro SIRCIP (campo 5 del DDJJ)
_TIPO_REGISTRO_PERCEPCION = "1"
_TIPO_REGISTRO_NO_INSCRIPTO = "4"
_TIPO_REGISTRO_SOBRETASA = "5"
_TIPO_REGISTRO_ANULADA = "6"


class AccountJournal(models.Model):
    _inherit = "account.journal"

    settlement_tax = fields.Selection(
        selection_add=[
            ("iibb_aplicado_sircip", "TXT Perc IIBB SIRCIP aplicadas"),
        ]
    )

    def iibb_aplicado_sircip_files_values(self, move_lines):
        """Genera el CSV de presentación de DDJJ para el SIRCIP.

        Formato CSV (17 campos por línea, separado por comas):
        1.  CUIT del contribuyente  Numérico(11)
        2.  CRC del contribuyente   Numérico(2)
        3.  Fecha de percepción     dd/mm/aaaa
        4.  Tipo de régimen         Numérico(3)  (l10n_ar_code del impuesto)
        5.  Tipo de registro        Numérico(2)  1=Perc,4=NoInscripto,5=Sobretasa,6=Anulada
        6.  Código op. exceptuada   Numérico(2)  (solo tipo 3=Excluido, vacío para el resto)
        7.  Jurisdicción            Numérico(3)
        8.  Tipo de comprobante     Numérico(3)  1=Fact,2=ND,102=NC,...
        9.  Letra del comprobante   Char(1)
        10. Punto de venta          Numérico(5)
        11. Número de comprobante   Numérico(8)
        12. Monto sujeto a percep.  Numérico(13) con punto decimal
        13. Alícuota (%)            Numérico(3,2) con punto decimal
        14. Monto percibido         Numérico(10) con punto decimal
        15. Nro. comprobante orig.  Alfanumérico(17) (solo anulaciones/devoluciones)
        16. CRC devolución          Numérico(2)  (solo devoluciones)
        17. ABM                     Alfanumérico(1) A=Alta,M=Modificación,B=Baja

        Ejemplo: 30100100106,34,03/03/2026,11,1,,904,1,A,00002,03431222,12342.03,2.00,246.84,,,A

        Fuente: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf
        """
        self.ensure_one()

        content = ""
        for line in move_lines.filtered(lambda x: x.move_id.is_invoice()):
            tax = line._get_settlement_tax()
            move = line.move_id
            partner = move.partner_id.commercial_partner_id

            # --- Campo 1: CUIT ---
            cuit = partner.ensure_vat()

            # --- Campo 2: CRC ---
            # El CRC proviene del registro l10n_ar.partner.tax cuyo ref tiene
            # formato "SIRCIP | crc:XX | campo7:YYY..."
            crc = self._sircip_crc_from_line(line)

            # --- Campo 3: Fecha de percepción ---
            fecha = fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # --- Campo 4: Tipo de régimen de percepción ---
            if not tax.l10n_ar_code:
                raise RedirectWarning(
                    message=_(
                        "Tax '%(tax)s' does not have an AFIP Code (l10n_ar_code) "
                        "configured. It is required to generate the SIRCIP TXT.",
                        tax=tax.name,
                    ),
                    action=tax.get_formview_action(),
                    button_text=_("Edit Tax"),
                )
            tipo_regimen = tax.l10n_ar_code

            # --- Campo 5: Tipo de registro ---
            internal_type = move.move_type
            if internal_type == "out_refund":
                tipo_registro = _TIPO_REGISTRO_ANULADA
            elif "No Inscripto" in tax.name:
                tipo_registro = _TIPO_REGISTRO_NO_INSCRIPTO
            elif "Sobre Alícuota" in tax.name:
                tipo_registro = _TIPO_REGISTRO_SOBRETASA
            else:
                tipo_registro = _TIPO_REGISTRO_PERCEPCION

            # --- Campo 6: Código de operación exceptuada (solo tipo 3=Excluido) ---
            cod_op_exceptuada = ""

            # --- Campo 7: Jurisdicción ---
            state = tax.l10n_ar_state_id
            if not state or not state.jurisdiction_code:
                raise ValidationError(
                    _(
                        "Tax '%(tax)s' does not have a jurisdiction configured, "
                        "or the province does not have a jurisdiction code.",
                        tax=tax.name,
                    )
                )
            jurisdiccion = state.jurisdiction_code

            # --- Campo 8: Tipo de comprobante ---
            doc_type = line.l10n_latam_document_type_id
            doc_internal_type = doc_type.internal_type if doc_type else "invoice"
            tipo_comprobante = _TIPO_COMPROBANTE_SIRCIP.get(doc_internal_type, 1)

            # --- Campo 9: Letra del comprobante ---
            letra = doc_type.l10n_ar_letter if doc_type else ""

            # --- Campos 10 y 11: Punto de venta y número de comprobante ---
            pos, number = get_pos_and_number(move.l10n_latam_document_number or "")

            # --- Campo 12: Monto sujeto a percepción (base imponible) ---
            base = line.withholding_id.base_amount if line.withholding_id else abs(get_line_tax_base(line))

            # --- Campo 13: Alícuota en porcentaje ---
            alicuota = tax.amount

            # --- Campo 14: Monto percibido ---
            monto = abs(line.balance)

            # --- Campos 15 y 16: nro. comprobante original y CRC devolución ---
            # Solo para anulaciones/devoluciones (nota de crédito)
            nro_original = ""
            crc_devolucion = ""
            if tipo_registro == _TIPO_REGISTRO_ANULADA:
                original = move._found_related_invoice() if hasattr(move, "_found_related_invoice") else None
                if original:
                    nro_original = original.l10n_latam_document_number or ""
                    crc_devolucion = crc  # mismo CRC del contribuyente

            # --- Campo 17: ABM ---
            abm = "A"  # Alta — Modificación y Baja se gestionan desde el portal

            row = [
                cuit,
                crc,
                fecha,
                tipo_regimen,
                tipo_registro,
                cod_op_exceptuada,
                jurisdiccion,
                str(tipo_comprobante),
                letra,
                "%05d" % int(pos or 0),
                "%08d" % int(number or 0),
                "%.2f" % base,
                "%.2f" % alicuota,
                "%.2f" % monto,
                nro_original,
                crc_devolucion,
                abm,
            ]
            content += ",".join(row) + "\r\n"

        return [{"txt_filename": "SIRCIP_DDJJ.txt", "txt_content": content}]

    def _sircip_crc_from_line(self, line):
        """Extrae el CRC del registro l10n_ar.partner.tax cacheado para este partner.

        El ref tiene formato: 'SIRCIP | crc:XX | campo7:YYY...'
        """
        partner = line.move_id.partner_id.commercial_partner_id
        partner_tax = self.env["l10n_ar.partner.tax"].search(
            [
                ("partner_id", "=", partner.id),
                ("tax_id.tax_group_id.name", "=", "SIRCIP"),
                ("ref", "like", "SIRCIP |"),
            ],
            order="from_date desc",
            limit=1,
        )
        if partner_tax and "crc:" in (partner_tax.ref or ""):
            try:
                return partner_tax.ref.split("crc:")[-1].split("|")[0].strip()
            except Exception:
                pass
        return ""
