from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import RedirectWarning, UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAccountBatchPaymentUx(AccountTestInvoicingCommon):
    def _create_batch(self, matched=0):
        payment_vals = {
            "amount": 100.0,
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_a.id,
            "journal_id": self.company_data["default_journal_bank"].id,
        }
        payments = self.env["account.payment"].create([payment_vals, payment_vals])
        if matched:
            # Liquidity line on the journal default account: the payment counts as matched.
            payments[:matched].outstanding_account_id = self.company_data["default_journal_bank"].default_account_id
        payments.action_post()
        return self.env["account.batch.payment"].create(
            {
                "journal_id": payments.journal_id.id,
                "payment_method_id": payments.payment_method_id.id,
                "payment_ids": [(6, 0, payments.ids)],
            }
        )

    def test_unlink_blocked_outside_draft(self):
        """Behaviors:
        - Given a batch that is not in draft, when it is deleted, then it raises.
        - Given a payment in a batch that is not in draft, when it is deleted, then it raises.
        - Given a draft batch, its payments and the batch itself can be deleted.
        """
        batch = self._create_batch()
        batch.validate_batch()
        self.assertEqual(batch.state, "sent")

        with self.subTest("a sent batch cannot be deleted"):
            with self.assertRaisesRegex(UserError, "delete a batch payment if is not on draft"):
                batch.unlink()
            self.assertTrue(batch.exists())

        with self.subTest("a payment of a sent batch cannot be deleted"):
            # A draft payment is deletable for core: only the module blocks it.
            payment = batch.payment_ids[0]
            payment.action_draft()
            with self.assertRaisesRegex(UserError, "delete payments from a batch payment"):
                payment.unlink()
            self.assertTrue(payment.exists())
            self.assertEqual(len(batch.payment_ids), 2)

        with self.subTest("in draft, the payments and the batch can be deleted"):
            draft_batch = self._create_batch()
            self.assertEqual(draft_batch.state, "draft")
            payment = draft_batch.payment_ids[0]
            payment.action_draft()
            payment.unlink()
            self.assertFalse(payment.exists())
            draft_batch.unlink()
            self.assertFalse(draft_batch.exists())

    def test_reset_to_draft_chain(self):
        """Behaviors:
        - Given a sent batch with a matched payment, when it is reset to draft,
          then it raises a RedirectWarning and nothing changes.
        - Given a sent batch without matched payments, when it is reset to draft,
          then the batch is draft, payments and their moves are unsent and keep their state.
        - The stored computed state stays draft after recomputation.
        """
        with self.subTest("with a matched payment, reset to draft stops and the batch stays sent"):
            matched_batch = self._create_batch(matched=1)
            self.assertEqual(matched_batch.payment_ids.mapped("is_matched"), [True, False])
            matched_batch.validate_batch()
            self.assertEqual(matched_batch.state, "sent")
            with self.assertRaises(RedirectWarning):
                matched_batch.action_draft()
            self.assertEqual(matched_batch.state, "sent")
            self.assertTrue(all(matched_batch.payment_ids.mapped("is_sent")))

        batch = self._create_batch()
        batch.validate_batch()
        batch.payment_ids.move_id.is_move_sent = True
        payment_states = batch.payment_ids.mapped("state")
        self.assertEqual(batch.state, "sent")

        with self.subTest("without matched payments, the batch goes back to draft and payments are unsent"):
            batch.action_draft()
            self.assertEqual(batch.state, "draft")
            self.assertFalse(any(batch.payment_ids.mapped("is_sent")))
            self.assertFalse(any(batch.payment_ids.move_id.mapped("is_move_sent")))

        with self.subTest("after recomputation, the batch stays draft and payments keep their state"):
            batch.invalidate_recordset()
            self.env.add_to_compute(batch._fields["state"], batch)
            self.env.flush_all()
            self.assertEqual(batch.state, "draft")
            self.assertEqual(batch.payment_ids.mapped("state"), payment_states)
            self.assertEqual(len(batch.payment_ids), 2)
