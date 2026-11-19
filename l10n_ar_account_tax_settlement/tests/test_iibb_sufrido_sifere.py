from odoo import Command, fields
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestIibbSufridoSifere(TestArCommon):
    """Suffered IIBB perceptions go to the SIFERE TXT with the jurisdiction of their province, except the SIRCIP
    ones: SIFERE Web loads them by itself, so reporting them would deduct them twice."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company_id = cls.company_ri.id
        cls.sircip_tax = cls.env.ref(
            "l10n_ar_account_tax_settlement.tax_percepcion_iibb_sircip_sufrida_%s" % company_id
        )
        cls.vat_tax = cls.env.ref("account.%s_ri_tax_vat_21_compras" % company_id)
        cls.provincial_taxes = {
            code: cls.env.ref("account.%s_ri_tax_percepcion_iibb_%s_sufrida" % (company_id, code))
            for code in ("caba", "ba", "co")
        }
        cls.iibb_journal = cls.env["account.journal"].search(
            [("company_id", "=", company_id), ("code", "=", "IIBB")], limit=1
        )
        cls.purchase_journal = cls.env["account.journal"].search(
            [("company_id", "=", company_id), ("type", "=", "purchase")], limit=1
        )

    def _vendor_bill(self, number, perception_taxes):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.res_partner_adhoc.id,
                "journal_id": self.purchase_journal.id,
                "invoice_date": fields.Date.today(),
                "l10n_latam_document_type_id": self.env.ref("l10n_ar.dc_a_f").id,
                "l10n_latam_document_number": number,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Perceptions",
                            "price_unit": 1000.0,
                            "tax_ids": [Command.set((self.vat_tax | perception_taxes).ids)],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def test_sircip_suffered_tax(self):
        """Every Argentinian company has the tax, excluded from SIFERE but settled in the IIBB journal."""
        self.assertEqual(self.sircip_tax.type_tax_use, "purchase")
        self.assertTrue(self.sircip_tax.l10n_ar_sifere_excluded)
        tax_line = self.sircip_tax.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == "tax")
        self.assertTrue(tax_line.account_id)
        self.assertTrue(set(self.iibb_journal.settlement_account_tag_ids.ids) & set(tax_line.tag_ids.ids))

    def test_sifere_txt_without_sircip(self):
        """The TXT brings the provincial perceptions with their jurisdiction and none of SIRCIP, and the notes say
        which bills carry the excluded ones."""
        bills = self._vendor_bill("0001-00000101", self.provincial_taxes["caba"] | self.sircip_tax)
        bills |= self._vendor_bill("0001-00000102", self.provincial_taxes["ba"] | self.provincial_taxes["co"])
        bills |= self._vendor_bill("0001-00000103", self.sircip_tax)
        perception_taxes = self.sircip_tax.union(*self.provincial_taxes.values())
        lines = bills.line_ids.filtered(lambda x: x.tax_line_id in perception_taxes)
        perceptions = self.iibb_journal.iibb_sufrido_files_values(lines)[0]
        rows = [row for row in perceptions["txt_content"].split("\r\n") if row]
        self.assertEqual(sorted(row[:3] for row in rows), ["901", "902", "904"])
        for bill in bills[0] | bills[2]:
            self.assertIn(bill.display_name, perceptions["notes"])
        self.assertNotIn(bills[1].display_name, perceptions["notes"])
