from freezegun import freeze_time

from odoo import Command
from odoo.addons.account_followup.tests.test_followup_report import TestAccountFollowupReports


def monkey_patches():
    def test_followup_lines_branches(self):
        branch = self.env["res.company"].create({"name": "branch", "parent_id": self.env.company.id})
        self.cr.precommit.run()  # load the COA

        report = self.env["account.followup.report"]
        options = {
            "partner_id": self.partner_a.id,
        }

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": "2016-01-01",
                "partner_id": self.partner_a.id,
                "company_id": branch.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "quantity": 1,
                            "price_unit": 500,
                            "tax_ids": [],
                        }
                    )
                ],
            }
        )
        invoice.action_post()

        # Dynamically fetch the currency symbol
        # currency_symbol = invoice.currency_id.symbol

        self.assertLinesValues(
            report._get_followup_report_lines(options),
            [0, 1, 2, 3, 5],
            [
                ("INV/2016/00001", "01/01/2016", "01/01/2016", "", "$\xa0500.00"),
                ("", "", "", "", "$\xa0500.00"),
                ("", "", "", "", "$\xa0500.00"),
            ],
            options,
        )

    def test_followup_report_with_no_due_date_on_invoice(self):
        """
        Invoices with no due date or payment term shouldn't be added to total_overdue
        on the followup report and on the partner.
        """
        report = self.env["account.followup.report"]
        options = {
            "partner_id": self.partner_a.id,
        }

        invoice1 = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": "2016-01-01",
                "invoice_payment_term_id": False,
                "partner_id": self.partner_a.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "quantity": 1,
                            "price_unit": 500,
                            "tax_ids": [],
                        }
                    )
                ],
            }
        )
        invoice1.action_post()

        invoice2 = self.env["account.move"].create(
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
        invoice2.action_post()

        with freeze_time("2016-01-15"):
            self.assertLinesValues(
                # pylint: disable=C0326
                report._get_followup_report_lines(options),
                #   Name                                    Date,           Due Date,       Doc.      Total Due
                [0, 1, 2, 3, 5],
                [
                    ("INV/2016/00002", "01/01/2016", "01/01/2016", "", "$\xa0300.00"),
                    ("INV/2016/00001", "01/01/2016", "01/01/2016", "", "$\xa0500.00"),
                    ("", "", "", "", "$\xa0800.00"),
                    ("", "", "", "", "$\xa0800.00"),
                ],
                options,
            )
            self.assertEqual(self.partner_a.total_due, 800)
            self.assertEqual(self.partner_a.total_overdue, 800)

    TestAccountFollowupReports.test_followup_lines_branches = test_followup_lines_branches
    TestAccountFollowupReports.test_followup_report_with_no_due_date_on_invoice = (
        test_followup_report_with_no_due_date_on_invoice
    )
