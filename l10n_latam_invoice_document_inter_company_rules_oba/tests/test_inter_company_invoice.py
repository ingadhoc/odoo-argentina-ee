from odoo import tests
from odoo.addons.account_inter_company_rules.tests.common import TestInterCompanyRulesCommon
from odoo.exceptions import ValidationError


@tests.tagged("post_install_l10n", "post_install", "-at_install")
class TestLatamInterCompanyInvoice(TestInterCompanyRulesCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        fiscal_country = cls.company_b.account_fiscal_country_id
        cls.doc_type_invoice = cls.env["l10n_latam.document.type"].create(
            {
                "name": "Test Invoice",
                "country_id": fiscal_country.id,
                "internal_type": "invoice",
                "doc_code_prefix": "INV",
            }
        )
        cls.latam_sale_journal_a = cls.env["account.journal"].create(
            {
                "name": "LATAM Sales Journal",
                "type": "sale",
                "code": "LTSI",
                "company_id": cls.company_a.id,
                "l10n_latam_use_documents": True,
            }
        )
        cls.latam_purchase_journal_b = cls.env["account.journal"].create(
            {
                "name": "LATAM Purchase Journal",
                "type": "purchase",
                "code": "LTPI",
                "company_id": cls.company_b.id,
                "l10n_latam_use_documents": True,
            }
        )
        cls.company_b.intercompany_purchase_journal_id = cls.latam_purchase_journal_b

        (cls.company_a + cls.company_b).write(
            {
                "intercompany_generate_bills_refund": True,
            }
        )

    def test_intercompany_bill_posted_with_document_number(self):
        """When intercompany_document_state is 'posted', the auto-created vendor bill
        must be posted without raising 'Please set the document number' and must carry
        the source invoice's document number.
        """
        self.company_b.intercompany_document_state = "posted"

        invoice = self._create_invoice_one_line(
            move_type="out_invoice",
            partner_id=self.company_b.partner_id,
            journal_id=self.latam_sale_journal_a,
            l10n_latam_document_type_id=self.doc_type_invoice,
            l10n_latam_document_number="00001-00001551",
            product_id=self.product_consultant,
            price_unit=1000.0,
            tax_ids=False,
        )
        invoice.with_user(self.res_users_company_a).action_post()

        self.assertEqual(invoice.state, "posted")

        vendor_bill = (
            self.env["account.move"]
            .sudo()
            .search(
                [
                    ("move_type", "=", "in_invoice"),
                    ("company_id", "=", self.company_b.id),
                    ("auto_generated", "=", True),
                ],
                limit=1,
            )
        )

        self.assertTrue(vendor_bill)
        self.assertEqual(vendor_bill.state, "posted")
        self.assertEqual(
            vendor_bill.l10n_latam_document_number,
            invoice.l10n_latam_document_number,
        )
        self.assertEqual(
            vendor_bill.l10n_latam_document_type_id,
            invoice.l10n_latam_document_type_id,
        )

    def test_intercompany_bill_no_document_when_journal_not_using_documents(self):
        """When the destination journal does not use LATAM documents the
        auto-created vendor bill must NOT carry the source invoice's document
        type.

        Note: l10n_latam_document_number is computed from the move name and
        will always reflect the journal sequence for posted moves; only the
        document type field is meaningful to assert here.
        """
        self.company_b.intercompany_document_state = "posted"

        # Point Company B to a plain purchase journal (no l10n_latam_use_documents)
        plain_purchase_journal_b = self.env["account.journal"].create(
            {
                "name": "Plain Purchase Journal",
                "type": "purchase",
                "code": "PLNP",
                "company_id": self.company_b.id,
                "l10n_latam_use_documents": False,
            }
        )
        self.company_b.intercompany_purchase_journal_id = plain_purchase_journal_b

        invoice = self._create_invoice_one_line(
            move_type="out_invoice",
            partner_id=self.company_b.partner_id,
            journal_id=self.latam_sale_journal_a,
            l10n_latam_document_type_id=self.doc_type_invoice,
            l10n_latam_document_number="00001-00001552",
            product_id=self.product_consultant,
            price_unit=1000.0,
            tax_ids=False,
        )
        invoice.with_user(self.res_users_company_a).action_post()

        self.assertEqual(invoice.state, "posted")

        vendor_bill = (
            self.env["account.move"]
            .sudo()
            .search(
                [
                    ("move_type", "=", "in_invoice"),
                    ("company_id", "=", self.company_b.id),
                    ("auto_generated", "=", True),
                ],
                limit=1,
            )
        )

        self.assertTrue(vendor_bill)
        self.assertFalse(vendor_bill.l10n_latam_document_type_id)

    def test_intercompany_bill_cross_country_raises(self):
        """Cross-country intercompany LATAM support is out of scope.

        When source (Company A) and destination (Company B) belong to different
        fiscal countries the document type of the source invoice is tied to
        Company A's country and therefore absent from the destination bill's
        l10n_latam_available_document_type_ids.  The document is not forwarded
        and posting raises a ValidationError because the destination LATAM
        journal requires a document type.
        """

        self.company_b.intercompany_document_state = "posted"

        country_a_alt = self.env.ref("base.br")
        self.company_a.account_fiscal_country_id = country_a_alt
        doc_type_country_a = self.env["l10n_latam.document.type"].create(
            {
                "name": "Test Invoice Country A",
                "country_id": country_a_alt.id,
                "internal_type": "invoice",
                "doc_code_prefix": "INVA",
            }
        )

        invoice = self._create_invoice_one_line(
            move_type="out_invoice",
            partner_id=self.company_b.partner_id,
            journal_id=self.latam_sale_journal_a,
            l10n_latam_document_type_id=doc_type_country_a,
            l10n_latam_document_number="00001-00001553",
            product_id=self.product_consultant,
            price_unit=1000.0,
            tax_ids=False,
        )

        with self.assertRaisesRegex(ValidationError, rf"following invoices \[{invoice.id + 1}\]\."):
            invoice.with_user(self.res_users_company_a).action_post()
