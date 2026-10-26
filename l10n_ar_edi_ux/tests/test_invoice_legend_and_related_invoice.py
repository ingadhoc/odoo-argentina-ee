from odoo import Command
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestInvoiceLegendAndRelatedInvoice(TestArCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal_online = cls._create_journal("wsfe", data={"l10n_ar_afip_pos_system": "RLI_RLM"})
        cls.journal_preprinted = cls._create_journal("preprinted")
        cls.company_ri.l10n_ar_invoice_pdf_legend = "payment_on_informed_cbu"

    def _render_invoice_pdf_html(self, invoice):
        html, __ = self.env["ir.actions.report"]._render_qweb_html(
            "account.report_invoice", invoice.ids, data={"report_type": "pdf"}
        )
        return html.decode() if isinstance(html, bytes) else html

    def _create_posted_invoice(self, journal):
        invoice = self._create_invoice_ar(partner_id=self.res_partner_adhoc, journal_id=journal.id)
        self._post(invoice)
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "1", "The test needs an invoice A")
        return invoice

    def test_legend_printed_on_online_journal(self):
        invoice = self._create_posted_invoice(self.journal_online)
        self.assertIn("Payment on Informed CBU", self._render_invoice_pdf_html(invoice))

    def test_legend_not_printed_on_preprinted_journal(self):
        invoice = self._create_posted_invoice(self.journal_preprinted)
        self.assertNotIn("Payment on Informed CBU", self._render_invoice_pdf_html(invoice))

    def test_credit_note_finds_invoice_through_sale_order(self):
        """A credit note made from the sale order lines finds the invoice of that order, so l10n_ar_edi
        does not ask for the associated period."""
        # The test user is an accountant, not a salesman
        order = (
            self.env["sale.order"]
            .sudo()
            .create(
                {
                    "partner_id": self.res_partner_adhoc.id,
                    "order_line": [Command.create({"product_id": self.product_iva_21.id, "price_unit": 100})],
                }
            )
        )
        order.action_confirm()
        invoice = self._create_invoice_ar(
            partner_id=self.res_partner_adhoc,
            journal_id=self.journal_online.id,
            invoice_line_ids=[
                Command.create(
                    {
                        "product_id": self.product_iva_21.id,
                        "price_unit": 100,
                        "sale_line_ids": [Command.set(order.order_line.ids)],
                    }
                )
            ],
        )
        self._post(invoice)
        # As if ARCA had accepted it
        invoice.sudo().write({"l10n_ar_afip_result": "A", "l10n_ar_afip_auth_code": "68448767638166"})

        credit_note = self._create_invoice_ar(
            move_type="out_refund",
            partner_id=self.res_partner_adhoc,
            journal_id=self.journal_online.id,
            invoice_line_ids=[
                Command.create(
                    {
                        "product_id": self.product_iva_21.id,
                        "price_unit": 100,
                        "sale_line_ids": [Command.set(order.order_line.ids)],
                    }
                )
            ],
        )
        self.assertFalse(credit_note.reversed_entry_id)
        self.assertEqual(credit_note._found_related_invoice(), invoice)
