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
    def test_wizard_assigns_and_stops_without_draft(self):
        """The wizard assigns each number to its draft; a number with no draft is left for the user to load."""
        lost = self._create_invoices(3)
        self._lose_and_stay_down(lost)
        first, second, deleted = lost
        deleted.unlink()
        wizard = self._wizard(first)
        self.assertEqual((wizard.number_from, wizard.number_to), (2, 4))
        wizard.action_fetch()
        assign_1, assign_2, missing = wizard.line_ids.sorted("number")
        self.assertEqual((assign_1.action, assign_1.move_id), ("match", first))
        self.assertEqual((assign_2.action, assign_2.move_id), ("match", second))
        self.assertEqual(missing.action, "skip")
        self.assertIn("Load it as a draft", missing.note)
        wizard.action_apply()
        self.assertEqual((first + second).mapped("state"), ["posted", "posted"])
        self.assertEqual([self._number(first), self._number(second)], [2, 3])
        self.assertEqual(first.l10n_ar_afip_auth_code, self.arca.registered[2]["CAE"])

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
