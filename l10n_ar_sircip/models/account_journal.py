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
from odoo.exceptions import ValidationError

from .account_fiscal_position_l10n_ar_tax import _SIRCIP_EXCLUIDO_TAX_NAME

_logger = logging.getLogger(__name__)

# Mapping tipo de comprobante Odoo → código SIRCIP DDJJ
# Fuente: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf campo 8
_TIPO_COMPROBANTE_SIRCIP = {
    "invoice": 1,  # Factura
    "debit_note": 2,  # Nota de Débito
    "credit_note": 102,  # Nota de Crédito
}

# Tipo de Registro SIRCIP (campo 5 del DDJJ)
# Fuente: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf
_TIPO_REGISTRO_PERCEPCION = "1"
_TIPO_REGISTRO_INFORMATIVO = "2"  # Alícuota 0% en padrón: declarar pero no cobrar
_TIPO_REGISTRO_EXCLUIDO = "3"  # Operación excluida: declarar con $0, sin factura
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
        4.  Tipo de régimen         Numérico(3)  Siempre "1" = Régimen General
        5.  Tipo de registro        Numérico(2)  1=Perc,2=Inform,3=Excluido,4=NoInscr,5=Sobretasa,6=Anulada
        6.  Código op. exceptuada   Numérico(2)  (solo tipo 3=Excluido)
        7.  Jurisdicción            Numérico(3)  Provincia de entrega
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

        Ejemplo: 30100100106,34,03/03/2026,1,1,,906,1,A,00002,03431222,12342.03,0.30,37.03,,,A

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
            crc = self._sircip_crc_from_line(line)

            # --- Campo 3: Fecha de percepción ---
            fecha = fields.Date.from_string(line.date).strftime("%d/%m/%Y")

            # --- Campo 4: Tipo de régimen de percepción ---
            # Siempre "1" = Régimen General. Por el momento es el único régimen
            # implementado en SIRCIP.
            # Fuente: CESSI Q&A — "En el campo 4 se deberá cargar el valor
            # 1 = Régimen General, que por el momento es el único régimen
            # que implementará el SIRCIP."
            tipo_regimen = "1"

            # --- Campo 5: Tipo de registro ---
            internal_type = move.move_type
            if internal_type == "out_refund":
                tipo_registro = _TIPO_REGISTRO_ANULADA
            elif tax.name == _SIRCIP_EXCLUIDO_TAX_NAME:
                # Dígito 3 del campo 7: operación excluida.
                # Fuente: CESSI Q&A — "declarar en DJ con Tipo de Registro = 3-Excluido,
                # no es necesario incorporar nada en la factura."
                tipo_registro = _TIPO_REGISTRO_EXCLUIDO
            elif tax.amount == 0.0 and tax.tax_group_id.name == "SIRCIP":
                # Alícuota 0% (letra A del padrón): informativo.
                # Fuente: CESSI Q&A — "Si la alícuota del padrón sea 0%, se debe declarar
                # la operación con Tipo de Registro = 2 - Informativo."
                tipo_registro = _TIPO_REGISTRO_INFORMATIVO
            elif "No Inscripto" in tax.name:
                tipo_registro = _TIPO_REGISTRO_NO_INSCRIPTO
            elif "Sobre Alícuota" in tax.name:
                tipo_registro = _TIPO_REGISTRO_SOBRETASA
            else:
                tipo_registro = _TIPO_REGISTRO_PERCEPCION

            # --- Campo 6: Código de operación exceptuada (solo tipo 3=Excluido) ---
            cod_op_exceptuada = ""

            # --- Campo 7: Jurisdicción — provincia de entrega de la operación ---
            # Para SIRCIP se usa la provincia de entrega (partner_shipping_id o
            # domicilio del partner), no tax.l10n_ar_state_id (que apunta a la
            # provincia ficticia SIRCIP).
            # Fuente: CESSI Q&A — "el campo 7 Jurisdicción es donde se realizó la entrega."
            shipping = move.partner_shipping_id or partner
            delivery_state = shipping.state_id if shipping else None
            if delivery_state and delivery_state.jurisdiction_code:
                jurisdiccion = delivery_state.jurisdiction_code
            else:
                # Fallback: verificar si el impuesto tiene jurisdicción real
                state = tax.l10n_ar_state_id
                sircip_state = self.env.ref("l10n_ar_sircip.state_ar_sircip", raise_if_not_found=False)
                if not state or not state.jurisdiction_code or state == sircip_state:
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
            letra_comp = doc_type.l10n_ar_letter if doc_type else ""

            # --- Campos 10 y 11: Punto de venta y número de comprobante ---
            pos, number = get_pos_and_number(move.l10n_latam_document_number or "")

            # --- Campo 12: Monto sujeto a percepción (base imponible) ---
            base = line.withholding_id.base_amount if line.withholding_id else abs(get_line_tax_base(line))

            # --- Campo 13: Alícuota en porcentaje ---
            alicuota = tax.amount

            # --- Campo 14: Monto percibido ---
            monto = abs(line.balance)

            # --- Campos 15 y 16: nro. comprobante original y CRC devolución ---
            nro_original = ""
            crc_devolucion = ""
            if tipo_registro == _TIPO_REGISTRO_ANULADA:
                original = move._found_related_invoice() if hasattr(move, "_found_related_invoice") else None
                if original:
                    nro_original = original.l10n_latam_document_number or ""
                    crc_devolucion = crc

            # --- Campo 17: ABM ---
            # Por ahora siempre "A" (Alta). Los valores "M" y "B" están en desarrollo
            # por parte de ARCA/CA.
            # Fuente: CESSI Q&A — "En el campo 17 ABM siempre se deberá colocar una 'A'."
            abm = "A"

            row = [
                cuit,
                crc,
                fecha,
                tipo_regimen,
                tipo_registro,
                cod_op_exceptuada,
                jurisdiccion,
                str(tipo_comprobante),
                letra_comp,
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

        El ref tiene formato: 'SIRCIP | crc:XX | letra:F | campo7:YYY...'
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
