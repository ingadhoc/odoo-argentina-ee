##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import float_round

from .common import TestSircipCommon

# 0-based positions of the DDJJ TXT fields
CUIT, CRC, DATE, REGIME, RECORD, JURISDICTION, BASE, ALIQUOT, AMOUNT, ORIGINAL, ORIGINAL_CRC, ABM = (
    0,
    1,
    2,
    3,
    4,
    6,
    11,
    12,
    13,
    14,
    15,
    16,
)


@tagged("post_install", "-at_install")
class TestSircipDdjj(TestSircipCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.settlement_journal:
            cls.settlement_journal = cls.env["account.journal"].create(
                {"name": "SIRCIP", "code": "SIRC", "type": "general", "settlement_tax": "iibb_aplicado_sircip"}
            )

    def _ddjj_rows(self, moves):
        lines = moves.line_ids.filtered("tax_line_id.l10n_ar_sircip_record_type")
        content = self.settlement_journal.iibb_aplicado_sircip_files_values(lines)[0]["txt_content"]
        return [row.split(",") for row in content.split("\r\n") if row]

    def test_ddjj_records(self):
        """Each perception is declared with its record type, delivery jurisdiction and amount; letter A invoices
        go as informative and credit notes reference the original invoice."""
        surcharge = self._sircip_invoice(self.partners["digit2"], post=True)
        not_registered = self._sircip_invoice(self.partners["not_registered"], post=True)
        # No perception: its informative record comes from the month's invoices
        self._sircip_invoice(self.partners["letter_a"], price_unit=500.0, post=True)
        refund = surcharge._reverse_moves(
            [{"invoice_date": self.today, "l10n_latam_document_type_id": self.env.ref("l10n_ar.dc_a_nc").id}]
        )
        refund.action_post()
        rows = self._ddjj_rows(surcharge | not_registered | refund)
        by_record = {}
        for row in rows:
            by_record.setdefault((row[CUIT], row[RECORD]), []).append(row)
        digit2_cuit = self.partners["digit2"].vat

        with self.subTest("fixed fields: regime 1, ABM A, delivery jurisdiction and 17 fields"):
            for row in rows:
                self.assertEqual(len(row), 17)
                self.assertEqual(row[REGIME], "1")
                self.assertEqual(row[ABM], "A")
                self.assertEqual(row[JURISDICTION], "906")
        with self.subTest("amount is base x aliquot / 100, rounded to 2"):
            for row in rows:
                expected = float_round(float(row[BASE]) * float(row[ALIQUOT]) / 100.0, precision_digits=2)
                self.assertEqual(row[AMOUNT], "%.2f" % expected)
        with self.subTest("digit 2: one type 1 and one type 5 record, with the padron CRC"):
            self.assertEqual(len(by_record.get((digit2_cuit, "1"), [])), 1)
            self.assertEqual(len(by_record.get((digit2_cuit, "5"), [])), 1)
            self.assertEqual(by_record[(digit2_cuit, "5")][0][CRC], self.crc["digit2"])
        with self.subTest("not registered: type 4, no CRC"):
            (row,) = by_record[(self.partners["not_registered"].vat, "4")]
            self.assertEqual(row[CRC], "")
        with self.subTest("letter A: informative type 2, aliquot 0 and the invoice base"):
            (row,) = by_record[(self.partners["letter_a"].vat, "2")]
            self.assertEqual((row[ALIQUOT], row[AMOUNT], row[BASE]), ("0.00", "0.00", "500.00"))
        with self.subTest("credit note: type 6 with the original document and its CRC"):
            cancelled = by_record[(digit2_cuit, "6")]
            self.assertEqual(len(cancelled), 2)
            for row in cancelled:
                self.assertEqual(row[ORIGINAL], surcharge.l10n_latam_document_number)
                self.assertEqual(row[ORIGINAL_CRC], self.crc["digit2"])
        with self.subTest("delivery in Salta: declared in the Salta jurisdiction (917)"):
            salta = self._sircip_invoice(
                self.partners["digit2"], shipping=self._delivery(self.partners["digit2"], self.salta), post=True
            )
            (row,) = (row for row in self._ddjj_rows(salta) if row[CUIT] == digit2_cuit)
            self.assertEqual((row[RECORD], row[JURISDICTION]), ("1", "917"))
        with self.subTest("digit 4: its provincial perception is not declared, only the SIRCIP one"):
            partner = self.partners["digit4"]
            invoice = self._sircip_invoice(
                partner, post=True, fiscal_position=self._corrientes_fiscal_position(partner)
            )
            self.assertEqual(
                [(row[RECORD], row[JURISDICTION]) for row in self._ddjj_rows(invoice) if row[CUIT] == partner.vat],
                [("1", "905")],
            )

    def test_ddjj_credit_note_without_original(self):
        """A credit note without its original invoice is stopped, since the DDJJ would be rejected."""
        refund = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": self.partners["digit1"].id,
                "journal_id": self.sale_journal.id,
                "invoice_date": self.today,
                "fiscal_position_id": self.fiscal_position.id,
                "invoice_line_ids": [Command.create({"product_id": self.product_iva_21.id, "price_unit": 100.0})],
            }
        )
        refund.action_post()
        with self.assertRaisesRegex(ValidationError, "original invoice"):
            self._ddjj_rows(refund)
