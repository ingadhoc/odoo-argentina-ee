##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from dateutil.relativedelta import relativedelta
from odoo import _, fields, models
from odoo.addons.l10n_ar_account_tax_settlement.models.account_journal import (
    get_line_tax_base,
    get_pos_and_number,
)
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools import float_round

# Mapping tipo de comprobante Odoo → código SIRCIP DDJJ
# Fuente: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf campo 8
_DOCUMENT_TYPES = {
    "invoice": 1,  # Factura
    "debit_note": 2,  # Nota de Débito
    "credit_note": 102,  # Nota de Crédito
}

# Tipos de registro sin impuesto propio (campo 5); el resto viene de account.tax.l10n_ar_sircip_record_type
_RECORD_INFORMATIVE = "2"
_RECORD_CANCELLED = "6"


class AccountJournal(models.Model):
    _inherit = "account.journal"

    settlement_tax = fields.Selection(
        selection_add=[
            ("iibb_aplicado_sircip", "TXT Perc IIBB SIRCIP aplicadas"),
        ]
    )

    def iibb_aplicado_sircip_files_values(self, move_lines):
        """TXT de presentación de DDJJ del SIRCIP: CSV de 17 campos, un registro por percepción.

        1. CUIT · 2. CRC del período · 3. Fecha · 4. Régimen (siempre 1, Régimen General) · 5. Tipo de
        registro · 6. Cód. op. exceptuada · 7. Jurisdicción de entrega · 8. Tipo de comprobante · 9. Letra ·
        10. Punto de venta · 11. Número · 12. Base · 13. Alícuota · 14. Monto (12 x 13 / 100, redondeado a
        2) · 15. Comprobante original (NC) · 16. CRC de la devolución · 17. ABM (siempre A)

        Tipos de registro: 1, 4 y 5 salen del impuesto de la línea; 6 (anulada) de las notas de crédito;
        2 (informativo, letra A del padrón) de las facturas del período a esos clientes, que no llevan
        percepción. El 3 (excluido) depende de los "ajustes al padrón", que todavía no se procesan.

        Fuentes: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf y Q&A CESSI de la Comisión Arbitral.
        """
        self.ensure_one()
        rows = []
        for line in move_lines.filtered(lambda x: x.move_id.is_invoice() and x.tax_line_id.l10n_ar_sircip_record_type):
            tax = line.tax_line_id
            record_type = (
                _RECORD_CANCELLED if line.move_id.move_type == "out_refund" else tax.l10n_ar_sircip_record_type
            )
            rows.append(
                self._sircip_ddjj_row(line.move_id, line.date, record_type, abs(get_line_tax_base(line)), tax.amount)
            )
        rows += self._sircip_informative_rows(move_lines)
        content = "".join(",".join(row) + "\r\n" for row in rows)
        return [{"txt_filename": "SIRCIP_DDJJ.txt", "txt_content": content}]

    def _sircip_ddjj_row(self, move, date, record_type, base, aliquot):
        partner = move.commercial_partner_id
        delivery_state = (move.partner_shipping_id or move.partner_id).state_id or partner.state_id
        if not delivery_state.jurisdiction_code:
            raise ValidationError(
                _(
                    "The delivery province of %(move)s has no jurisdiction code, required by the SIRCIP DDJJ.",
                    move=move.display_name,
                )
            )
        doc_type = move.l10n_latam_document_type_id
        pos, number = get_pos_and_number(move.l10n_latam_document_number or "")
        original_number = original_crc = ""
        if record_type == _RECORD_CANCELLED:
            original = move.reversed_entry_id or (
                move._found_related_invoice() if hasattr(move, "_found_related_invoice") else move.browse()
            )
            if not original:
                # La Comisión Arbitral rechaza la DDJJ si la NC no informa el comprobante original.
                raise ValidationError(
                    _(
                        "Credit note %(move)s has no original invoice. It is mandatory in the SIRCIP DDJJ.",
                        move=move.display_name,
                    )
                )
            original_number = original.l10n_latam_document_number or ""
            original_crc = self._sircip_crc(original)
        return [
            partner.ensure_vat(),
            self._sircip_crc(move),
            date.strftime("%d/%m/%Y"),
            "1",
            record_type,
            "",
            delivery_state.jurisdiction_code,
            str(_DOCUMENT_TYPES.get(doc_type.internal_type, 1)),
            doc_type.l10n_ar_letter or "",
            "%05d" % int(pos or 0),
            "%08d" % int(number or 0),
            "%.2f" % base,
            "%.2f" % aliquot,
            "%.2f" % float_round(base * aliquot / 100.0, precision_digits=2),
            original_number,
            original_crc,
            "A",
        ]

    def _sircip_padron_data(self, move):
        """Datos del padrón SIRCIP guardados en el partner para el mes del comprobante."""
        cache = self.env["l10n_ar.partner.tax"].search(
            [
                ("partner_id", "=", move.commercial_partner_id.id),
                ("tax_id.l10n_ar_sircip_record_type", "!=", False),
                ("from_date", "<=", move.date),
                ("to_date", ">=", move.date),
            ],
            limit=1,
        )
        return self.env["account.fiscal.position.l10n_ar_tax"]._sircip_parse_ref(cache.ref)

    def _sircip_crc(self, move):
        return self._sircip_padron_data(move)["crc"]

    def _sircip_informative_rows(self, move_lines):
        """Registros tipo 2: facturas de los meses liquidados a clientes con letra A (0%) y entrega en una
        provincia adherida. No llevan percepción, pero la Comisión Arbitral pide declararlas."""
        if not move_lines:
            return []
        months = {date + relativedelta(day=1) for date in move_lines.mapped("date")}
        domain = expression.OR(
            [[("date", ">=", month), ("date", "<=", month + relativedelta(months=1, days=-1))] for month in months]
        )
        invoices = self.env["account.move"].search(
            expression.AND(
                [
                    domain,
                    [
                        ("company_id", "=", self.company_id.id),
                        ("move_type", "=", "out_invoice"),
                        ("state", "=", "posted"),
                        ("fiscal_position_id.l10n_ar_tax_ids.default_tax_id.l10n_ar_sircip_record_type", "!=", False),
                    ],
                ]
            ),
            order="date, id",
        )
        rows = []
        for move in invoices:
            data = self._sircip_padron_data(move)
            delivery_state = (
                move.partner_shipping_id or move.partner_id
            ).state_id or move.commercial_partner_id.state_id
            if data["in_padron"] and not data["aliquot"] and delivery_state.l10n_ar_is_sircip:
                rows.append(
                    self._sircip_ddjj_row(move, move.date, _RECORD_INFORMATIVE, abs(move.amount_untaxed_signed), 0.0)
                )
        return rows
