from odoo.addons.l10n_ar_edi.tests.common import TestArEdiCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "post_install_l10n", "-at_install")
class TestCaeLock(TestArEdiCommon):
    @classmethod
    @TestArEdiCommon.setup_afip_ws("wsfe")
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.res_partner_adhoc
        cls.journal = cls._create_journal("wsfe")

    def _new_invoice(self):
        return self._create_invoice_ar(
            journal_id=self.journal,
            invoice_line_ids=[self._prepare_invoice_line(product_id=self.product_iva_21, price_unit=100)],
        )

    def _set_cae(self, invoice, result=False):
        """Simulate an invoice that was posted with a CAE and then reset to draft."""
        invoice.write(
            {
                "l10n_ar_afip_auth_mode": "CAE",
                "l10n_ar_afip_auth_code": "76123456789012",
                "l10n_ar_afip_result": result,
            }
        )
        invoice.posted_before = True

    def test_unlink_blocked_when_accepted_in_arca(self):
        for result in ("A", "O"):
            invoice = self._new_invoice()
            self._set_cae(invoice, result)
            with self.assertRaises(UserError):
                invoice.unlink()

    def test_unlink_allowed_with_manual_cae(self):
        """A CAE typed by hand has no ARCA result: it can still be fixed or deleted."""
        invoice = self._new_invoice()
        self._set_cae(invoice)
        invoice.unlink()
        self.assertFalse(invoice.exists())

    def test_unlink_allowed_without_cae(self):
        invoice = self._new_invoice()
        invoice.unlink()
        self.assertFalse(invoice.exists())
