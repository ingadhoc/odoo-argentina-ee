from odoo import Command
from odoo.addons.l10n_ar_withholding.tests.test_withholding_ar_ri import TestArWithholdingArRi
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestPaymentWithholdingSettlement(TestArWithholdingArRi):
    """Editing a posted payment re-creates its withholding journal items without the settlement link.

    The withholding then shows up as pending to settle although it was already declared, which is how
    the same amount ends up declared twice.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settlement_tag = cls.env["account.account.tag"].create(
            {
                "name": "Withholding settlement tag",
                "applicability": "taxes",
                "country_id": cls.env.company.account_fiscal_country_id.id,
            }
        )
        cls.tax_wth_test_1.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == "tax").tag_ids = [
            Command.set(cls.settlement_tag.ids)
        ]
        cls.settlement_journal = cls.env["account.journal"].create(
            {
                "name": "Withholding Settlement Journal",
                "code": "WSJ",
                "type": "general",
                "tax_settlement": "allow_per_line",
                "settlement_partner_id": cls.res_partner_adhoc.id,
                "settlement_account_id": cls.company_data["default_account_payable"].id,
                "settlement_account_tag_ids": [Command.set(cls.settlement_tag.ids)],
            }
        )

    def _create_posted_payment_with_withholding(self, document_number):
        invoice = self.in_invoice_wht(document_number)
        payable_line = invoice.line_ids.filtered(lambda x: x.account_type == "liability_payable")
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": invoice.partner_id.id,
                "amount": invoice.amount_total,
                "date": "2023-01-01",
                "journal_id": self.company_data["default_journal_bank"].id,
            }
        )
        payment.to_pay_move_line_ids = [Command.set(payable_line.ids)]
        withholding = self.env["l10n_ar.payment.withholding"].create(
            {"payment_id": payment.id, "tax_id": self.tax_wth_test_1.id}
        )
        withholding.base_amount = 1000.0
        withholding._compute_amount()
        payment.action_post()
        return payment

    def _get_withholding_line(self, payment):
        return payment.move_id.line_ids.filtered("tax_repartition_line_id")

    def _settle_and_edit(self, payment, edit):
        """Settle the withholding of the payment and then edit the payment, as the user does."""
        withholding_line = self._get_withholding_line(payment)
        self.assertEqual(len(withholding_line), 1)
        settlement = withholding_line.button_create_tax_settlement_entry()
        self.assertEqual(withholding_line.tax_settlement_move_id, settlement)
        self.assertFalse(payment.unlinked_tax_settlement_count)
        payment.action_draft()
        payment.write(edit)
        payment.action_post()
        return settlement

    def test_withholding_is_reassigned_to_its_settlement(self):
        payment = self._create_posted_payment_with_withholding("2-101")
        settlement = self._settle_and_edit(payment, {"payment_reference": "edited"})

        new_line = self._get_withholding_line(payment)
        self.assertFalse(new_line.tax_settlement_move_id, "editing the payment re-creates the line without the link")
        self.assertEqual(payment.unlinked_tax_settlement_count, 1)
        self.assertEqual(payment.unlinked_tax_settlement_line_ids, new_line)
        self.assertEqual(new_line.tax_state, "to_settle")

        payment.action_reassign_tax_settlement()

        self.assertEqual(new_line.tax_settlement_move_id, settlement)
        self.assertFalse(payment.unlinked_tax_settlement_count)
        self.assertFalse(payment.move_id.unlinked_tax_settlement_ids, "nothing is left pending after reassigning")
        self.assertEqual(
            sum(settlement.settled_line_ids.mapped("balance")),
            -sum(settlement.line_ids.filtered(lambda x: x.account_id == new_line.account_id).mapped("balance")),
            "the settlement adds up again",
        )

    def test_settlement_is_guessed_from_the_gap_it_left(self):
        payment = self._create_posted_payment_with_withholding("2-102")
        settlement = self._settle_and_edit(payment, {"payment_reference": "edited"})
        # A payment broken before this module was installed has nothing kept on the entry.
        payment.move_id.unlinked_tax_settlement_ids.unlink()

        new_line = self._get_withholding_line(payment)
        self.assertEqual(new_line._get_tax_settlement_to_reassign(), settlement)

    def test_payment_without_settled_withholding_shows_no_warning(self):
        payment = self._create_posted_payment_with_withholding("2-103")
        payment.action_draft()
        payment.payment_reference = "edited"
        payment.action_post()

        self.assertFalse(payment.unlinked_tax_settlement_count)
        self.assertFalse(payment.move_id.unlinked_tax_settlement_ids)

    def test_reassign_wizard_offers_the_settlement_with_a_gap(self):
        payment = self._create_posted_payment_with_withholding("2-104")
        settlement = self._settle_and_edit(payment, {"payment_reference": "edited"})
        payment.move_id.unlinked_tax_settlement_ids.unlink()
        new_line = self._get_withholding_line(payment)

        wizard = self.env["l10n_ar.tax.settlement.reassign"].create(
            {"line_ids": [Command.set(new_line.ids)], "settlement_move_id": settlement.id}
        )
        self.assertIn(settlement, wizard.candidate_move_ids, "the settlement left with a gap is offered")
        wizard.action_reassign()

        self.assertEqual(new_line.tax_settlement_move_id, settlement)
