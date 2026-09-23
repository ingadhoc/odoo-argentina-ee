# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import csv
import io
from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestPartnerLedgerCsvExport(AccountTestInvoicingCommon):
    """The CSV export of the Partner Ledger: the report fully unfolded, batch by batch."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("account_reports.partner_ledger_report")
        receivable = cls.company_data["default_account_receivable"]
        cls.partner_c = cls.env["res.partner"].create({"name": "partner_c"})
        # With multi-currency the report shows the "Amount Currency" column, two cells in the CSV.
        cls.other_currency = cls.setup_other_currency("EUR")
        cls.env.user.group_ids |= cls.env.ref("base.group_multi_currency")

        def post_entry(date, lines):
            move = cls.env["account.move"].create(
                {
                    "move_type": "entry",
                    "date": fields.Date.from_string(date),
                    "journal_id": cls.company_data["default_journal_misc"].id,
                    "line_ids": [Command.create(vals) for vals in lines],
                }
            )
            move.action_post()
            return move

        # Before the period: initial balances.
        post_entry(
            "2016-06-01",
            [
                {"account_id": receivable.id, "partner_id": cls.partner_a.id, "debit": 100.0},
                {"account_id": receivable.id, "partner_id": cls.partner_b.id, "credit": 100.0},
            ],
        )
        # In the period, including lines without partner reconciled with lines of partner_a and
        # partner_c: they show under each partner and, reversed, under "Unknown Partner".
        post_entry(
            "2017-02-01",
            [
                {"account_id": receivable.id, "partner_id": cls.partner_a.id, "debit": 1000.0},
                {"account_id": receivable.id, "partner_id": cls.partner_a.id, "debit": 500.0},
                {
                    "account_id": receivable.id,
                    "partner_id": cls.partner_b.id,
                    "debit": 300.0,
                    "currency_id": cls.other_currency.id,
                    "amount_currency": 600.0,
                },
                {"account_id": receivable.id, "partner_id": cls.partner_c.id, "debit": 250.0},
                {"account_id": cls.company_data["default_account_revenue"].id, "credit": 2050.0},
            ],
        )
        bank_account = cls.company_data["default_journal_bank"].default_account_id
        for partner, amount in ((cls.partner_a, 500.0), (cls.partner_c, 250.0)):
            without_partner = post_entry(
                "2017-03-01",
                [
                    {"account_id": receivable.id, "credit": amount},
                    {"account_id": bank_account.id, "debit": amount},
                ],
            )
            (
                cls.env["account.move.line"].search(
                    [
                        ("partner_id", "=", partner.id),
                        ("account_id", "=", receivable.id),
                        ("date", ">=", "2017-01-01"),
                        ("debit", "=", amount),
                    ]
                )
                | without_partner.line_ids.filtered(lambda line: line.account_id == receivable)
            ).reconcile()

    def _get_options(self, report=None):
        report = report or self.report
        return report.get_options(
            {
                "selected_variant_id": report.id,
                "date": {"date_from": "2017-01-01", "date_to": "2017-12-31", "mode": "range", "filter": "custom"},
            }
        )

    def _export_csv(self, options):
        file_content = self.report.dispatch_report_action(options, "generate_csv_export")["file_content"]
        # The export reads through a cursor of its own, like the native one of the General Ledger.
        with self.enter_registry_test_mode():
            return list(csv.reader(io.StringIO(b"".join(file_content).decode())))

    def _balance(self, line, options):
        balance_index = next(i for i, col in enumerate(options["columns"]) if col["expression_label"] == "balance")
        return line["columns"][balance_index].get("no_format") or 0.0

    def test_the_partner_ledger_offers_a_csv_export(self):
        """Offered with ``branch_allowed``, so it passes the gate of "Copy to Documents" too."""
        exports = {
            button["name"]: button for button in self._get_options()["buttons"] if button.get("file_export_type")
        }
        self.assertIn("CSV", exports)
        self.assertTrue(exports["CSV"]["branch_allowed"])

    def test_the_follow_up_reports_do_not_get_the_csv_export(self):
        """They inherit the handler, but the export is about the ledger."""
        reports = [
            self.env.ref(xmlid, raise_if_not_found=False)
            for xmlid in ("account_reports.followup_report", "account_reports.customer_statement_report")
        ]
        reports = [report for report in reports if report]
        if not reports:
            self.skipTest("no follow-up report")
        for report in reports:
            with self.subTest(report=report.name):
                options = self._get_options(report)
                self.assertNotIn("generate_csv_export", [button.get("action_param") for button in options["buttons"]])

    def test_the_csv_is_the_report_fully_unfolded(self):
        """Row by row, the same lines and running balances the printed report shows unfolded.

        Except the "Total <partner>" under each unfolded partner: its row already carries them.
        The batch size is taken down to one partner to cross batch boundaries.
        """
        options = self._get_options()
        print_options = self.report.get_options({**options, "export_mode": "print", "unfold_all": True})
        expected = [
            (line["name"], self._balance(line, print_options))
            for line in self.report._get_lines(print_options)
            if not (line.get("parent_id") and self.report._parse_line_id(line["id"])[-1][0] == "total")
        ]

        with patch("odoo.addons.account_accountant_ux.models.account_partner_ledger.CSV_PARTNER_BATCH_SIZE", 1):
            rows = self._export_csv(options)

        header, rows = rows[0], rows[1:]
        balance_index = header.index(
            next(col["name"] for col in options["columns"] if col["expression_label"] == "balance")
        )
        exported = [(row[1] or row[0], float(row[balance_index] or 0.0)) for row in rows]

        self.assertEqual([name for name, _balance in exported], [name for name, _balance in expected])
        for (name, balance), (_name, expected_balance) in zip(exported, expected):
            self.assertAlmostEqual(balance, expected_balance, msg=name)

    def test_the_texts_do_not_run_as_formulas(self):
        """A partner typed as a formula gets a leading quote; the amounts do not."""
        partner = self.env["res.partner"].create({"name": '=HYPERLINK("http://evil")'})
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2017-05-01"),
                "journal_id": self.company_data["default_journal_misc"].id,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": self.company_data["default_account_receivable"].id,
                            "partner_id": partner.id,
                            "credit": 70.0,
                        }
                    ),
                    Command.create({"account_id": self.company_data["default_account_revenue"].id, "debit": 70.0}),
                ],
            }
        )
        move.action_post()

        options = self._get_options()
        rows = self._export_csv(options)
        header, rows = rows[0], rows[1:]
        balance_index = header.index(
            next(col["name"] for col in options["columns"] if col["expression_label"] == "balance")
        )
        rows = [row for row in rows if row[0] == "'" + partner.name]
        self.assertTrue(rows, "the partner cell is escaped")
        self.assertIn("-70.00", [row[balance_index] for row in rows], "the negative balance is not")

    def test_every_row_carries_its_partner(self):
        """So the file can be filtered by partner without the tree of the screen."""
        rows = self._export_csv(self._get_options())[1:-1]
        self.assertIn("partner_a", {row[0] for row in rows})
        self.assertTrue(all(row[0] for row in rows))

    def test_the_parts_of_the_background_export_join_into_the_same_file(self):
        """The hooks read by documents_account_bg: one part per batch, header first, total last."""
        options = self._get_options()
        export_options = self.report.get_options({**options, "export_mode": "file"})
        handler = self.env[self.report._get_custom_handler_model()]

        with patch("odoo.addons.account_accountant_ux.models.account_partner_ledger.CSV_PARTNER_BATCH_SIZE", 1):
            split = handler._get_bg_export_chunks(export_options, "generate_csv_export")
            parts = [
                handler._get_bg_export_chunk(export_options, "generate_csv_export", chunk) for chunk in split["chunks"]
            ]
            file_content = self.report.dispatch_report_action(export_options, "generate_csv_export")["file_content"]
            with self.enter_registry_test_mode():
                expected = b"".join(file_content)

        self.assertEqual(len(split["chunks"]), 4, "one per partner, and Unknown Partner alone")
        self.assertTrue(split["file_name"].endswith(".csv"))
        self.assertEqual(b"".join(parts), expected)
        self.assertIsNone(handler._get_bg_export_chunks(export_options, "export_to_xlsx"))
