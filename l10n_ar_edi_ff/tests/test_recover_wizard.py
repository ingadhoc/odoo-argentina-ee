from odoo.exceptions import RedirectWarning, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import BatchCaeCommon


@tagged("post_install", "post_install_l10n", "-at_install")
class TestRecoverWizard(BatchCaeCommon):
    def _wizard(self, invoices):
        wizard = self.env["l10n_ar_edi_ff.recover"].create(
            {"journal_id": self.journal.id, "document_type_id": invoices[0].l10n_latam_document_type_id.id}
        )
        wizard._onchange_range()
        return wizard

    @mute_logger("odoo.addons.l10n_ar_edi_ff.models.account_move")
    def test_validation_offers_the_wizard(self):
        """When the gap cannot be recovered on its own, the error opens the wizard."""
        lost = self._create_invoices(1)
        self._lose_and_stay_down(lost)
        lost.unlink()
        new = self._create_invoices(1, price=500)
        with self.assertRaises(RedirectWarning):
            new.with_context(l10n_ar_invoice_skip_commit=True).action_post()

    @mute_logger("odoo.addons.l10n_ar_edi_ff.models.account_move")
    def test_wizard_assigns_and_creates(self):
        """The wizard assigns a number to its draft and creates the document that has none in Odoo."""
        lost = self._create_invoices(2)
        self._lose_and_stay_down(lost)
        kept, deleted = lost
        deleted.unlink()
        wizard = self._wizard(kept)
        self.assertEqual((wizard.number_from, wizard.number_to), (2, 3))
        wizard.action_fetch()
        assign, create = wizard.line_ids.sorted("number")
        self.assertEqual((assign.action, assign.move_id), ("match", kept))
        self.assertEqual(create.action, "create")
        wizard.account_id = self.env["account.account"].search(
            [("company_ids", "in", self.company_ri.ids), ("account_type", "=", "income")], limit=1
        )
        wizard.action_apply()
        self.assertEqual(kept.state, "posted")
        self.assertEqual(create.applied_move_id.state, "posted")
        self.assertEqual(create.applied_move_id.amount_total, kept.amount_total)
        self.assert_batch_coherence()

    @mute_logger("odoo.addons.l10n_ar_edi_ff.models.account_move")
    def test_wizard_takes_numbers_in_order(self):
        """A skipped number stops the ones after it: Odoo numbers in order."""
        lost = self._create_invoices(2)
        self._lose_and_stay_down(lost)
        wizard = self._wizard(lost)
        wizard.action_fetch()
        first, _second = wizard.line_ids.sorted("number")
        first.action = "skip"
        with self.assertRaisesRegex(UserError, "taken in order"):
            wizard.action_apply()
