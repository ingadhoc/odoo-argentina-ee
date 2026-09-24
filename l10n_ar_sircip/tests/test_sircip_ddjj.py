##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import float_round

from .common import TestSircipCommon

# Posiciones (0-based) de los 17 campos del TXT de DDJJ
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
        """El TXT declara cada percepción con su tipo de registro, la jurisdicción de entrega y el monto que
        valida la Comisión Arbitral; las facturas a clientes con letra A van como informativas y las NC
        referencian la factura original. Fuente: diseño de registros SIRCIP y Q&A CESSI."""
        surcharge = self._sircip_invoice(self.partners["digit2"], post=True)
        not_registered = self._sircip_invoice(self.partners["not_registered"], post=True)
        # sin percepción: el registro informativo sale de cruzar las facturas del mes
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

        with self.subTest("campos fijos: régimen 1, ABM A, jurisdicción de entrega y 17 campos"):
            for row in rows:
                self.assertEqual(len(row), 17)
                self.assertEqual(row[REGIME], "1")
                self.assertEqual(row[ABM], "A")
                self.assertEqual(row[JURISDICTION], "906")
        with self.subTest("el monto es base x alícuota / 100, redondeado a 2"):
            for row in rows:
                expected = float_round(float(row[BASE]) * float(row[ALIQUOT]) / 100.0, precision_digits=2)
                self.assertEqual(row[AMOUNT], "%.2f" % expected)
        with self.subTest("dígito 2: un registro tipo 1 y otro tipo 5, con el CRC del padrón"):
            self.assertEqual(len(by_record.get((digit2_cuit, "1"), [])), 1)
            self.assertEqual(len(by_record.get((digit2_cuit, "5"), [])), 1)
            self.assertEqual(by_record[(digit2_cuit, "5")][0][CRC], self.crc["digit2"])
        with self.subTest("no inscripto: tipo 4, sin CRC"):
            (row,) = by_record[(self.partners["not_registered"].vat, "4")]
            self.assertEqual(row[CRC], "")
        with self.subTest("letra A: informativo tipo 2, alícuota 0 y la base de la factura"):
            (row,) = by_record[(self.partners["letter_a"].vat, "2")]
            self.assertEqual((row[ALIQUOT], row[AMOUNT], row[BASE]), ("0.00", "0.00", "500.00"))
        with self.subTest("NC: tipo 6 con el comprobante original y su CRC"):
            cancelled = by_record[(digit2_cuit, "6")]
            self.assertEqual(len(cancelled), 2)
            for row in cancelled:
                self.assertEqual(row[ORIGINAL], surcharge.l10n_latam_document_number)
                self.assertEqual(row[ORIGINAL_CRC], self.crc["digit2"])

    def test_ddjj_credit_note_without_original(self):
        """La Comisión Arbitral rechaza la DDJJ si una NC no informa el comprobante original: se frena antes."""
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
