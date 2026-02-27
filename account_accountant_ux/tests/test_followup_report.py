from odoo import tools
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestPatchDummy(common.TransactionCase):
    def test_dummy(self):
        # a trivial test so the test runner reports >0 tests (avoids the 0-tests warning)
        self.assertTrue(True)


# Only apply the patch while running tests
if tools.config.get("test_enable"):
    from odoo.addons.account_followup.tests.test_followup_report import TestAccountFollowupReports

    def test_manual_followup_invoice_attachments_pdf_report_file(self):
        invoices, attachments = self._prepare_invoices_and_attachments()
        wizard = (
            self.env["account_followup.manual_reminder"]
            .with_context(
                active_model="res.partner",
                active_ids=invoices[1].partner_id.ids,
            )
            .create({})
        )

        self.assertEqual(invoices[1].partner_id.unreconciled_aml_ids.move_id, invoices)
        self.assertEqual(
            wizard.attachment_ids,
            invoices.message_main_attachment_id,
            "The manually uploaded PDF should not be attached to the follow-up.",
        )

    def propagate(method1, method2):
        if method1:
            for attr in ("_returns",):
                if hasattr(method1, attr) and not hasattr(method2, attr):
                    setattr(method2, attr, getattr(method1, attr))
        return method2

    def _patch_method(cls, name, method):
        origin = getattr(cls, name)
        method.origin = origin
        wrapped = propagate(origin, method)
        wrapped.origin = origin
        setattr(cls, name, wrapped)

    _patch_method(
        TestAccountFollowupReports,
        "test_manual_followup_invoice_attachments_pdf_report_file",
        test_manual_followup_invoice_attachments_pdf_report_file,
    )

    # This module adds a forced_domain that excludes journal entries
    # (move_type='entry' without payment_ids), so MISC/2016/01/0001 is
    # filtered out. Additionally, _get_partner_aml_report_lines is overridden
    # to append "Total Due" and "Total Overdue" summary lines.
    # Result: 3 lines instead of the original 4.
    def test_followup_report_with_entries(self):
        from freezegun import freeze_time
        from odoo.fields import Command  # noqa: F811

        report = self.env["account.followup.report"]
        options = {
            "partner_id": self.partner_a.id,
        }
        with freeze_time("2016-01-02"):
            invoice = self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "invoice_date": "2016-01-01",
                    "invoice_date_due": "2016-01-01",
                    "invoice_payment_term_id": False,
                    "partner_id": self.partner_a.id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "quantity": 1,
                                "price_unit": 300,
                                "tax_ids": [],
                            }
                        )
                    ],
                }
            )
            invoice.action_post()

            entry = self.env["account.move"].create(
                {
                    "move_type": "entry",
                    "date": "2016-01-02",
                    "partner_id": self.partner_a.id,
                    "line_ids": [
                        Command.create(
                            {
                                "name": "line1",
                                "account_id": self.company_data["default_account_receivable"].id,
                                "debit": 500.0,
                                "credit": 0.0,
                            }
                        ),
                        Command.create(
                            {
                                "name": "counterpart line",
                                "account_id": self.company_data["default_account_revenue"].id,
                                "debit": 0.0,
                                "credit": 500.0,
                            }
                        ),
                    ],
                }
            )
            entry.action_post()

        with freeze_time("2016-01-15"):
            # The account_no_followup module sets no_followup=True for entry-type
            # moves (is_entry() and no origin_payment_id). Our custom
            # _get_unreconciled_aml_domain adds ("no_followup", "=", False), so
            # the journal entry is excluded from unreconciled_aml_ids, total_due,
            # and the report. Only the invoice ($300) appears.
            # The upstream _get_followup_report_lines sets name='' on summary
            # lines (the label sits in columns[3], which this test skips at index 4).
            self.assertLinesValues(
                # pylint: disable=C0326
                report._get_followup_report_lines(options),
                #   Name            Date            Due Date        Doc.    Total Due
                [0, 1, 2, 3, 5],
                [
                    ("INV/2016/00001", "01/01/2016", "01/01/2016", "", "$\xa0300.00"),
                    ("", "", "", "", "$\xa0300.00"),
                    ("", "", "", "", "$\xa0300.00"),
                ],
                options,
            )
            self.assertEqual(self.partner_a.total_due, 300)
            self.assertEqual(self.partner_a.total_overdue, 300)

    _patch_method(TestAccountFollowupReports, "test_followup_report_with_entries", test_followup_report_with_entries)
