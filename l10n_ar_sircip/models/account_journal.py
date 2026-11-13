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

# ARCA document code -> SIRCIP DDJJ document code (field 8)
_DOCUMENT_CODES = {
    "4": 3,  # receipts A, B and C
    "9": 3,
    "15": 3,
    "5": 4,  # cash sale notes A and B
    "10": 4,
    "19": 5,  # export invoice
    "20": 6,  # export debit note
    "21": 106,  # export credit note
    "17": 7,  # settlements
    "18": 7,
    "27": 7,
    "28": 7,
    "29": 7,
    "63": 7,
    "64": 7,
}
# Fallback by Odoo document type; other debits go as 20 and other credits as 120
_DOCUMENT_TYPES = {
    "invoice": 1,
    "debit_note": 2,
    "credit_note": 102,
}

# Record type (field 5) with no tax of its own; the rest come from account.tax.l10n_ar_sircip_record_type
_RECORD_INFORMATIVE = "2"


class AccountJournal(models.Model):
    _inherit = "account.journal"

    settlement_tax = fields.Selection(
        selection_add=[
            ("iibb_aplicado_sircip", "TXT DDJJ SIRCIP (módulo SIRCIP)"),
        ]
    )

    def iibb_aplicado_sircip_files_values(self, move_lines):
        """SIRCIP DDJJ TXT: 17-field CSV, one record per perception.

        Fields: 1 CUIT, 2 period CRC, 3 date, 4 regime (always 1), 5 record type, 6 exempt operation code
        (always 0), 7 delivery jurisdiction, 8 document type, 9 letter, 10 point of sale, 11 number, 12 base,
        13 aliquot, 14 amount (12 x 13 / 100, rounded to 2), 15 original document (credit notes), 16 refund CRC
        (not used yet), 17 ABM (A).

        Record types 1, 4 and 5 come from the line tax, also on credit notes, which go with negative amounts and
        the original invoice. Type 2 (informative, letter A) comes from the period invoices to those customers.
        Type 3 (excluded) is not supported yet.
        Sources: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf and the Comision Arbitral operating guide.
        """
        self.ensure_one()
        rows = []
        for line in move_lines.filtered(lambda x: x.move_id.is_invoice() and x.tax_line_id.l10n_ar_sircip_record_type):
            tax = line.tax_line_id
            sign = -1 if line.move_id.move_type == "out_refund" else 1
            rows.append(
                self._sircip_ddjj_row(
                    line.move_id,
                    line.date,
                    tax.l10n_ar_sircip_record_type,
                    sign * abs(get_line_tax_base(line)),
                    tax.amount,
                )
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
        crc = self._sircip_crc(move)
        original_number = ""
        if move.move_type == "out_refund":
            original = move.reversed_entry_id or (
                move._found_related_invoice() if hasattr(move, "_found_related_invoice") else move.browse()
            )
            if not original:
                raise ValidationError(
                    _(
                        "Credit note %(move)s has no original invoice. It is mandatory in the SIRCIP DDJJ.",
                        move=move.display_name,
                    )
                )
            original_type = original.l10n_latam_document_type_id
            original_pos, original_doc_number = get_pos_and_number(original.l10n_latam_document_number or "")
            original_number = "%03d%s%05d%08d" % (
                self._sircip_document_code(original),
                original_type.l10n_ar_letter or "",
                int(original_pos or 0),
                int(original_doc_number or 0),
            )
            crc = self._sircip_crc(original)
        return [
            partner.ensure_vat(),
            crc,
            date.strftime("%d/%m/%Y"),
            "1",
            record_type,
            "0",
            delivery_state.jurisdiction_code,
            str(self._sircip_document_code(move)),
            doc_type.l10n_ar_letter or "",
            str(int(pos or 0)),
            str(int(number or 0)),
            "%.2f" % base,
            "%.2f" % aliquot,
            "%.2f" % float_round(base * aliquot / 100.0, precision_digits=2),
            original_number,
            "",
            "A",
        ]

    def _sircip_document_code(self, move):
        """SIRCIP DDJJ document code (field 8) of the move."""
        doc_type = move.l10n_latam_document_type_id
        code = _DOCUMENT_CODES.get(doc_type.code) or _DOCUMENT_TYPES.get(doc_type.internal_type)
        if code:
            return code
        return 120 if move.move_type == "out_refund" else 20

    def _sircip_padron_data(self, move):
        """SIRCIP padron data stored on the partner for the month of the move."""
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
        """Type 2 records: invoices of the settled months to letter A (0%) customers, delivered in any province,
        which carry no perception but must be declared."""
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
            if data["in_padron"] and not data["aliquot"]:
                rows.append(
                    self._sircip_ddjj_row(move, move.date, _RECORD_INFORMATIVE, abs(move.amount_untaxed_signed), 0.0)
                )
        return rows
