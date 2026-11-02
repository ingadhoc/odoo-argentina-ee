from dateutil.relativedelta import relativedelta
from odoo.exceptions import RedirectWarning, UserError
from odoo.tests import Form, tagged
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
        self.assertEqual((assign_1 + assign_2).mapped("move_id"), first + second)
        self.assertFalse(missing.move_id)
        self.assertIn("load it", missing.note)
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
        first.move_id = False
        with self.assertRaisesRegex(UserError, "has no draft"):
            wizard.action_apply()

    @mute_logger("odoo.addons.l10n_ar_edi_ff.models.account_move")
    def test_wizard_skips_an_old_draft_with_the_same_total(self):
        """An old draft of the same customer and total is not proposed: the date of ARCA has to match."""
        lost = self._create_invoices(1)
        self._lose_and_stay_down(lost)
        old = self._create_invoices(1)
        old.invoice_date = self.today - relativedelta(days=40)
        wizard = self._wizard(lost)
        wizard.action_fetch()
        self.assertEqual(wizard.line_ids.move_id, lost)

    @mute_logger("odoo.addons.l10n_ar_edi_ff.models.account_move")
    def test_wizard_does_not_assign_a_draft_that_changed(self):
        """A draft that, once posted, is not what ARCA authorized does not take the number."""
        lost = self._create_invoices(1)
        self._lose_and_stay_down(lost)
        wizard = self._wizard(lost)
        wizard.action_fetch()
        self.assertEqual(wizard.line_ids.move_id, lost)
        # A change after ARCA authorized it, like a perception added when the date is written
        lost.invoice_line_ids.price_unit += 1
        wizard.line_ids.amount_total = lost.amount_total
        with self.assertRaisesRegex(UserError, "not the document ARCA authorized"):
            wizard.action_apply()

    @mute_logger("odoo.addons.l10n_ar_edi_ff.models.account_move")
    def test_wizard_from_the_invoice_comes_with_the_documents(self):
        """Opened from the invoice that hit the gap, the wizard brings the documents with no question asked."""
        lost = self._create_invoices(2)
        self._lose_and_stay_down(lost)
        context = {
            "default_journal_id": self.journal.id,
            "default_document_type_id": lost[0].l10n_latam_document_type_id.id,
            "l10n_ar_edi_ff_recover_fetch": True,
        }
        with Form(self.env["l10n_ar_edi_ff.recover"].with_context(**context)) as form:
            self.assertEqual(form.state, "review")
            self.assertEqual(len(form.line_ids), 2)
        wizard = form.record
        self.assertEqual(wizard.line_ids.mapped("move_id"), lost)
        wizard.action_apply()
        self.assertEqual(set(lost.mapped("state")), {"posted"})
        self.assert_batch_coherence()
