import odoo.tests.common as common
from odoo import Command, fields


class L10nArAccountTaxSettlementUnitTest(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.company = self.env.company
        self.company.use_payment_pro = True
        self.company_bank_journal = self.env["account.journal"].search(
            [("company_id", "=", self.company.id), ("type", "=", "bank")], limit=1
        )
        self.company_sale_journal = self.env["account.journal"].search(
            [("company_id", "=", self.company.id), ("type", "=", "sale")], limit=1
        )
        self.partner_ri = self.env["res.partner"].search([("name", "=", "Deco Addict")])

    
    def test_l10n_ar_account_tax_settlement_account_payment_pro_receiptbook(self):
        """
        Test to verify the correct tax settlement behavior in payments when using receiptbooks
        and ensure that the l10n_latam_document_type_id is not being changing to False
        when passing invoice to draft.

        Steps:
        1. Create an invoice for the partner.
        2. Post the invoice.
        3. Register a payment for the invoice.
        4. Verify that the document type used matches the receiptbook's document type.
        5. Set the payment to draft and recalculate withholdings.
        6. Ensure the document type remains consistent after recomputation.
        """

        # Step 1: Create an invoice for the partner
        invoice = self.env["account.move"].create(
            {
                "partner_id": self.partner_ri.id,
                "invoice_date": self.today,
                "move_type": "out_invoice",
                "journal_id": self.company_sale_journal.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.env.ref("product.product_product_16").id,
                            "quantity": 1,
                            "price_unit": 10000000,
                        }
                    ),
                ],
            }
        )
        # Step 2: Post the invoice
        invoice.action_post()

        # Step 3: Register a payment for the invoice
        vals = {
            "journal_id": self.company_bank_journal.id,
            "amount": invoice.amount_total,
        }
        action_context = invoice.action_register_payment()["context"]
        payment = self.env["account.payment"].with_context(**action_context).create(vals)
        # Step 4: Post the payment
        payment.action_post()

        # Step 5: Verify that the document type matches the receiptbook's document type
        l10n_latam_document_type_id = payment.l10n_latam_document_type_id
        receiptbook = payment.receiptbook_id
        self.assertEqual(
            l10n_latam_document_type_id.id,
            receiptbook.document_type_id.id,
            "A different document type is used than the one in the receiptbook"
        )

        # Step 6: Set the payment to draft and recompute withholdings
        payment.action_draft()
        payment.compute_withholdings()

        # Step 7: Ensure the document type remains the same after recomputation
        self.assertEqual(
            l10n_latam_document_type_id,
            payment.l10n_latam_document_type_id,
            "A different document type is used than the one in the receiptbook"
        )
