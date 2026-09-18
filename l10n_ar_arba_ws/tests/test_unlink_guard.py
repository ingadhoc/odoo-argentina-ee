from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import L10nArArbaWsCommon


@tagged("-at_install", "post_install")
class TestUnlinkGuard(L10nArArbaWsCommon):
    """Task 71519: which DDJJ can be deleted, and which must not be.

    The guard was widened to accept cancelled declarations, so the states it still has
    to refuse are checked too: widening it is only correct if it did not turn into no
    guard at all.
    """

    def test_unlink_guard_by_state(self):
        for state, deletable in (("draft", True), ("cancel", True), ("open", False), ("close", False)):
            with self.subTest("a DDJJ in state %s is %sdeletable" % (state, "" if deletable else "not ")):
                ddjj = self._create_ddjj(state=state)
                if deletable:
                    ddjj.unlink()
                    self.assertFalse(ddjj.exists())
                else:
                    with self.assertRaisesRegex(UserError, "draft or cancelled state"):
                        ddjj.unlink()
                    self.assertTrue(ddjj.exists())

    def test_cancelled_ddjj_with_withholdings_is_not_deletable(self):
        """A withholding already reported to ARBA never loses its DDJJ."""
        ddjj = self._create_ddjj(state="cancel", name=self._next_arba_id())
        line = self._create_withholding_line(ddjj, cert_number="40021623")

        with self.assertRaisesRegex(UserError, "has withholding lines"):
            ddjj.unlink()

        self.assertEqual(line.l10n_ar_dj_arba_id, ddjj)
