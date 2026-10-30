from odoo import fields
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestBackwardTaxCopy(TestArCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invoice_date = fields.Date.from_string("2025-09-15")
        caba_perception = cls.env.ref(f"account.{cls.company_ri.id}_ri_tax_percepcion_iibb_caba_aplicada")
        # the template tax is archived, so copies must be activated explicitly
        cls.backward_tax = caba_perception.copy(
            default={
                "active": True,
                "amount_type": "percent",
                "amount": 3,
                "is_backward_tax": True,
                "name": "Backward CABA",
            }
        )
        cls.partner_tax = caba_perception.copy(
            default={"active": True, "amount_type": "percent", "amount": 5, "name": "CABA 5%"}
        )
        cls.iva_21 = cls.env.ref(f"account.{cls.company_ri.id}_ri_tax_vat_21_ventas")
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Customer CABA",
                "country_id": cls.env.ref("base.ar").id,
                "state_id": cls.env.ref("base.state_ar_c").id,
                "l10n_ar_afip_responsibility_type_id": cls.env.ref("l10n_ar.res_IVARI").id,
                "l10n_latam_identification_type_id": cls.env.ref("l10n_ar.it_cuit").id,
                "vat": "20055361682",
                "is_company": True,
            }
        )
        # invoice a child contact: partner taxes live on the commercial partner
        cls.contact = cls.env["res.partner"].create({"name": "Invoicing Contact", "parent_id": cls.customer.id})

    def _create_migrated_invoice(self):
        invoice = self._create_invoice(
            partner_id=self.contact,
            invoice_date=self.invoice_date,
            invoice_line_ids=[
                self._prepare_invoice_line(price_unit=100, tax_ids=self.iva_21 | self.backward_tax),
                self._prepare_invoice_line(price_unit=50, tax_ids=self.iva_21),
            ],
        )
        # migrated invoices keep the generic perception tax archived
        self.backward_tax.active = False
        return invoice

    def test_reverse_replaces_backward_tax_with_partner_tax(self):
        invoice = self._create_migrated_invoice()
        self.env["l10n_ar.partner.tax"].create(
            {
                "tax_id": self.partner_tax.id,
                "partner_id": self.customer.id,
                "company_id": self.company_ri.id,
                "from_date": fields.Date.from_string("2025-09-01"),
            }
        )
        refund = invoice._reverse_moves()
        first_line, second_line = refund.invoice_line_ids
        self.assertEqual(first_line.tax_ids, self.iva_21 | self.partner_tax)
        self.assertEqual(second_line.tax_ids, self.iva_21)

    def test_reverse_without_partner_tax_removes_backward_tax(self):
        invoice = self._create_migrated_invoice()
        refund = invoice._reverse_moves()
        self.assertEqual(refund.invoice_line_ids.tax_ids, self.iva_21)
        self.assertTrue(any("Backward CABA" in body for body in refund.message_ids.mapped("body")))

    def test_reverse_prefers_partner_tax_of_backward_tax_group(self):
        invoice = self._create_migrated_invoice()
        other_group = self.partner_tax.tax_group_id.copy(default={"name": "Other CABA group"})
        other_tax = self.partner_tax.copy(default={"name": "CABA other group", "tax_group_id": other_group.id})
        for tax in (other_tax, self.partner_tax):
            self.env["l10n_ar.partner.tax"].create(
                {"tax_id": tax.id, "partner_id": self.customer.id, "company_id": self.company_ri.id}
            )
        refund = invoice._reverse_moves()
        self.assertEqual(refund.invoice_line_ids[0].tax_ids, self.iva_21 | self.partner_tax)
