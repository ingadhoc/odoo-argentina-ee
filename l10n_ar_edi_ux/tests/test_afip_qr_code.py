import base64
import json

from odoo import Command
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAfipQrCode(TestArCommon):
    def test_qr_code_partner_identification_without_afip_code(self):
        """Export invoices for foreign partners whose identification type has no
        ARCA code (e.g. the generic "VAT" type) must still render the QR code.

        Odoo 19.0 _get_partner_code_id returns an implicit None in that case,
        crashing int() in _compute_l10n_ar_afip_qr_code when printing."""
        partner = self.res_partner_barcelona_food
        partner.write(
            {
                "l10n_latam_identification_type_id": self.env.ref("l10n_latam_base.it_vat").id,
                "vat": "ESA12345674",
            }
        )

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": self.sale_expo_journal_ri.id,
                "l10n_latam_document_type_id": self.document_type["invoice_e"].id,
                "invoice_date": "2026-08-04",
                "invoice_line_ids": [Command.create({"name": "Test product", "quantity": 1, "price_unit": 100.0})],
            }
        )
        invoice.l10n_latam_document_number = "00002-00000001"
        # Simulate an ARCA validated invoice (these values are normally set by the ws)
        invoice.write(
            {
                "l10n_ar_afip_auth_mode": "CAE",
                "l10n_ar_afip_auth_code": "12345678901234",
            }
        )

        qr_code = invoice.l10n_ar_afip_qr_code
        self.assertTrue(qr_code)
        qr_data = json.loads(base64.b64decode(qr_code.split("?p=")[1]))
        self.assertEqual(qr_data["tipoDocRec"], 0)
