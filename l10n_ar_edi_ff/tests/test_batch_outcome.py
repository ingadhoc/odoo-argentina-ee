from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import BatchCaeCommon


@tagged("post_install", "post_install_l10n", "-at_install")
class TestBatchOutcome(BatchCaeCommon):
    @mute_logger("odoo.addons.l10n_ar_edi_ff.models.account_move")
    def test_batch_outcome_by_arca_answer(self):
        """Whatever ARCA answers to a chunk, Odoo ends with the same numbers and CAE as ARCA."""
        with self.subTest("ARCA approves the three"):
            invoices = self._create_invoices(3)
            errors = self._post_batch(invoices)
            # One request for the whole chunk, every invoice posted with its CAE
            self.assertFalse(errors)
            self.assertEqual(self.arca.sends, 1)
            self.assertEqual(set(invoices.mapped("state")), {"posted"})
            self.assert_batch_coherence()

        with self.subTest("ARCA rejects the second, the third is sent again"):
            self.arca.reset()
            first, second, third = invoices = self._create_invoices(3)
            # A different total identifies the second for ARCA, whatever number it gets
            second.invoice_line_ids.price_unit = 300
            self.arca.reject = {second.amount_total}
            sends = self.arca.sends
            errors = self._post_batch(invoices)
            # The rejected one stays in draft with the request kept; the one after it goes in a second request
            self.assertEqual(self.arca.sends - sends, 2)
            self.assertEqual((first + third).mapped("state"), ["posted", "posted"])
            self.assertEqual(second.state, "draft")
            self.assertEqual(list(errors), second.ids)
            self.assertTrue(second.l10n_ar_afip_xml_request)
            self.assert_batch_coherence()

        with self.subTest("an invoice fails before the request, the others go on"):
            self.arca.reset()
            first, second, third = invoices = self._create_invoices(3)
            Move = self.registry["account.move"]
            check_rate = Move.l10n_ar_check_rate

            def failing_check_rate(move):
                if move == second:
                    raise UserError("Invalid rate")
                return check_rate(move)

            sends = self.arca.sends
            with patch.object(Move, "l10n_ar_check_rate", failing_check_rate):
                errors = self._post_batch(invoices)
            # It never reaches ARCA: one request with the other two
            self.assertEqual(self.arca.sends - sends, 1)
            self.assertEqual((first + third).mapped("state"), ["posted", "posted"])
            self.assertEqual(second.state, "draft")
            self.assertIn("Invalid rate", errors[second.id])
            self.assert_batch_coherence()

        with self.subTest("the answer is lost after ARCA registered two of three"):
            self.arca.reset()
            first, second, third = invoices = self._create_invoices(3)
            self.arca.lose_after = 2
            errors = self._post_batch(invoices)
            # The registered prefix is recovered; the third is not sent again
            self.assertEqual((first + second).mapped("state"), ["posted", "posted"])
            self.assertEqual(third.state, "draft")
            self.assertIn("No answer from ARCA", errors[third.id])
            self.assert_batch_coherence()

        with self.subTest("the answer is lost and ARCA stays down"):
            self.arca.reset()
            invoices = self._create_invoices(3)
            self.arca.lose_after = 3
            self.arca.down_after_send = True
            registered = len(self.arca.registered)
            errors = self._post_batch(invoices)
            # Nothing is confirmed: all in draft, each with the request and the reason
            self.assertEqual(set(invoices.mapped("state")), {"draft"})
            self.assertEqual(sorted(errors), sorted(invoices.ids))
            for invoice in invoices:
                self.assertIn("could not check what it registered", errors[invoice.id])
                self.assertTrue(invoice.l10n_ar_afip_xml_request)
            # Expected mismatch, closed by the next step: ARCA registered the three that Odoo still has in draft.
            self.assertEqual(len(self.arca.registered) - registered, 3)

        with self.subTest("when ARCA is back, validating again recovers what it registered"):
            self.arca.reset()
            errors = self._post_batch(invoices)
            # ARCA answers 10016 and the recovery brings its CAE instead of reporting them twice
            self.assertFalse(errors)
            self.assertEqual(set(invoices.mapped("state")), {"posted"})
            self.assert_batch_coherence()

    def test_coherence_detects_a_mismatch(self):
        """The coherence check must fail when Odoo and ARCA disagree, or it verifies nothing."""
        invoice = self._create_invoices(1)
        self._post_batch(invoice)
        self.assert_batch_coherence()
        invoice.l10n_ar_afip_auth_code = "1"
        with self.assertRaises(AssertionError):
            self.assert_batch_coherence()
