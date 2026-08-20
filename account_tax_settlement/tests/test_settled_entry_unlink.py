from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSettledEntryUnlink(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settlement_tag = cls.env["account.account.tag"].create(
            {
                "name": "Settlement tag",
                "applicability": "taxes",
                "country_id": cls.env.company.account_fiscal_country_id.id,
            }
        )
        cls.settled_tax = cls.env["account.tax"].create(
            {
                "name": "Settled tax 10%",
                "amount_type": "percent",
                "amount": 10.0,
                "type_tax_use": "purchase",
                "invoice_repartition_line_ids": [
                    Command.create({"repartition_type": "base"}),
                    Command.create({"repartition_type": "tax", "tag_ids": [Command.set(cls.settlement_tag.ids)]}),
                ],
                "refund_repartition_line_ids": [
                    Command.create({"repartition_type": "base"}),
                    Command.create({"repartition_type": "tax", "tag_ids": [Command.set(cls.settlement_tag.ids)]}),
                ],
            }
        )
        cls.settlement_journal = cls.env["account.journal"].create(
            {
                "name": "Tax Settlement Journal",
                "code": "TSJ",
                "type": "general",
                "tax_settlement": "allow_per_line",
                "settlement_partner_id": cls.partner_a.id,
                "settlement_account_id": cls.company_data["default_account_payable"].id,
                "settlement_account_tag_ids": [Command.set(cls.settlement_tag.ids)],
            }
        )

    def _create_settled_bill(self):
        """Return a posted bill and its tax line, already included in a settlement."""
        bill = self._create_invoice_one_line(
            move_type="in_invoice",
            partner_id=self.partner_a,
            price_unit=1000.0,
            tax_ids=self.settled_tax,
            post=True,
        )
        tax_line = bill.line_ids.filtered("tax_repartition_line_id")
        self.assertEqual(tax_line.tax_state, "to_settle")
        tax_line.create_tax_settlement_entry()
        self.assertTrue(tax_line.tax_settlement_move_id)
        return bill, tax_line

    def test_unlink_settled_entry_is_blocked(self):
        bill, dummy = self._create_settled_bill()
        bill.button_draft()
        with self.assertRaisesRegex(UserError, "already included in a tax settlement"):
            bill.unlink()

    def test_unlink_after_deleting_the_settlement(self):
        bill, tax_line = self._create_settled_bill()
        tax_line.tax_settlement_move_id.unlink()
        self.assertFalse(tax_line.tax_settlement_move_id)
        self.assertEqual(tax_line.tax_state, "to_settle")
        bill.button_draft()
        bill.unlink()

    def test_unlink_unsettled_entry_is_allowed(self):
        bill = self._create_invoice_one_line(
            move_type="in_invoice",
            partner_id=self.partner_a,
            price_unit=1000.0,
            tax_ids=self.settled_tax,
            post=True,
        )
        bill.button_draft()
        bill.unlink()
