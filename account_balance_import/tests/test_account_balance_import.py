import datetime
import io

import xlsxwriter
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import BinaryBytes


def generate_xlsx(data):
    """
    Generates an XLSX file from the given data dictionary. Each key in the `data` dictionary represents a column
    header, and its corresponding values are written as rows under that column.

    Date and datetime objects in the values will automatically set the style of the cell to a date/datetime.

    :param dict data: keys are column headers, values are rows.
    :return bytes: the xlsx file as bytes.
    """
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = wb.add_worksheet("Sheet1")

    date_style = wb.add_format({"num_format": "yyyy-mm-dd"})
    datetime_style = wb.add_format({"num_format": "yyyy-mm-dd hh:mm:ss"})

    for column, (key, values) in enumerate(data.items()):
        ws.write(0, column, key)
        for row, value in enumerate(values, 1):
            if isinstance(value, datetime.datetime):
                ws.write_datetime(row, column, value, datetime_style)
            elif isinstance(value, datetime.date):
                ws.write_datetime(row, column, value, date_style)
            else:
                ws.write(row, column, value)

    wb.close()
    return output.getvalue()


@tagged("post_install", "-at_install")
class TestAccountBalanceImport(TransactionCase):
    """Test cases for account balance import functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up company
        cls.company = cls.env.company

        # Create general journal for entries
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test General Journal",
                "code": "TGJ",
                "type": "general",
                "company_id": cls.company.id,
            }
        )

        # Get or create counterpart account (unaffected earnings)
        cls.counterpart_account = cls.company.get_unaffected_earnings_account()

        # Create test partners
        cls.partners = cls.env["res.partner"].create(
            [{"name": f"Test Partner {i}", "company_id": cls.company.id} for i in range(1, 6)]
        )
        cls.partner_1, cls.partner_2, cls.partner_3, cls.partner_4, cls.partner_5 = cls.partners

        # Create accounts for account_balance tests
        cls.account_1 = cls.env["account.account"].create(
            {
                "code": "TEST001",
                "name": "Test Account 1",
                "account_type": "asset_current",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

        cls.account_2 = cls.env["account.account"].create(
            {
                "code": "TEST002",
                "name": "Test Account 2",
                "account_type": "liability_current",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

        # Account in a currency other than the company one, to load opening balances at a
        # rate the user types instead of the one the system holds. The currency is taken by
        # xml id and activated: a database can perfectly hold the company currency as the
        # only active one, and searching among the active ones came back empty there, which
        # left the account without currency and made every test below fail on the
        # amount_in_currency constraint.
        cls.foreign_currency = cls.env.ref("base.USD")
        if cls.foreign_currency == cls.company.currency_id:
            cls.foreign_currency = cls.env.ref("base.EUR")
        cls.foreign_currency.active = True
        cls.account_fx = cls.env["account.account"].create(
            {
                "code": "TESTFX",
                "name": "Test Account Foreign Currency",
                "account_type": "asset_current",
                "currency_id": cls.foreign_currency.id,
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        # A bank account in the same currency: its lines carry a residual
        # (`_compute_amount_residual` only runs on reconcilable and cash accounts), which is
        # what the opening amount is reconciled against later on.
        cls.account_fx_bank = cls.env["account.account"].create(
            {
                "code": "TESTFXB",
                "name": "Test Bank Account Foreign Currency",
                "account_type": "asset_cash",
                "currency_id": cls.foreign_currency.id,
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

    def _save_opening(self, account, values):
        """Write on the opening columns the way the chart of accounts list does, and let the
        precommit callbacks that build the opening move run, as they do at the end of the
        request."""
        account.write(values)
        self.env.cr.precommit.run()
        self.env.invalidate_all()

    def _opening_lines(self, account):
        return self.company.account_opening_move_id.line_ids.filtered(lambda l: l.account_id == account)

    def test_opening_debit_keeps_typed_amount_in_currency(self):
        """The amount typed in the account currency is kept on a debit opening balance"""
        self._save_opening(self.account_fx, {"amount_in_currency": 100.0, "opening_debit": 4000.0})

        self.assertEqual(self.account_fx.opening_debit, 4000.0)
        self.assertAlmostEqual(self.account_fx.amount_in_currency, 100.0, places=2)

        line = self._opening_lines(self.account_fx)
        self.assertEqual(len(line), 1, "Should have exactly one opening line")
        self.assertAlmostEqual(line.amount_currency, 100.0, places=2)

    def test_both_sides_are_rejected_on_an_account_with_its_own_currency(self):
        """One amount per account describes one side: loading both is rejected, not guessed"""
        self._save_opening(self.account_fx, {"amount_in_currency": 100.0, "opening_debit": 4000.0})

        # The savepoint rolls the failed save back the way the request does.
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._save_opening(self.account_fx, {"amount_in_currency": 50.0, "opening_credit": 1000.0})

    def test_the_side_already_loaded_is_kept_after_the_rejection(self):
        """The amount loaded on one side survives an attempt to load the other one"""
        self._save_opening(self.account_fx, {"amount_in_currency": 100.0, "opening_debit": 4000.0})

        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._save_opening(self.account_fx, {"amount_in_currency": 50.0, "opening_credit": 1000.0})

        self.assertEqual(self.account_fx.opening_debit, 4000.0)
        self.assertEqual(self.account_fx.opening_credit, 0.0)
        line = self._opening_lines(self.account_fx)
        self.assertEqual(len(line), 1, "Should have exactly one opening line")
        self.assertAlmostEqual(line.amount_currency, 100.0, places=2)

    def test_opening_residual_follows_the_typed_amount_in_currency(self):
        """The residual stored on the line must follow the amount the SQL update forced"""
        self._save_opening(self.account_fx_bank, {"amount_in_currency": 100.0, "opening_debit": 4000.0})
        # Second save: the line is updated instead of created, which is where the amount used
        # to be lost.
        self._save_opening(self.account_fx_bank, {"amount_in_currency": 250.0, "opening_debit": 10000.0})

        line = self._opening_lines(self.account_fx_bank)
        self.assertAlmostEqual(line.amount_currency, 250.0, places=2)
        self.assertAlmostEqual(
            line.amount_residual_currency,
            250.0,
            places=2,
            msg="The residual is stored and computed from amount_currency, so the raw UPDATE "
            "has to mark it for recompute: otherwise the opening line of an account in a "
            "foreign currency is left with a residual that does not match its amount, and "
            "that is dragged into the reconciliation against the payments",
        )
        self.assertAlmostEqual(line.amount_residual, 10000.0, places=2)

    def test_opening_amount_in_currency_alone_is_applied(self):
        """Editing only the amount in the account currency also updates the opening move"""
        self._save_opening(self.account_fx, {"amount_in_currency": 100.0, "opening_debit": 4000.0})
        self._save_opening(self.account_fx, {"amount_in_currency": 250.0})

        self.assertEqual(self.account_fx.opening_debit, 4000.0, "The balance must not be touched")
        self.assertAlmostEqual(self.account_fx.amount_in_currency, 250.0, places=2)
        self.assertAlmostEqual(self._opening_lines(self.account_fx).amount_currency, 250.0, places=2)

    def test_opening_move_stays_balanced(self):
        """Forcing the amount in currency must not unbalance the opening entry"""
        self._save_opening(self.account_fx, {"amount_in_currency": 100.0, "opening_credit": 4000.0})

        move = self.company.account_opening_move_id
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_credit_amount_in_currency_takes_the_sign_of_the_balance(self):
        """A credit amount in currency typed negative, as the template shows it, is loaded too"""
        self._save_opening(self.account_fx, {"amount_in_currency": -100.0, "opening_credit": 4000.0})

        self.assertAlmostEqual(self._opening_lines(self.account_fx).amount_currency, -100.0, places=2)

    def test_accounting_manager_loads_opening_balances(self):
        """An accounting manager without Settings rights can create the opening move"""
        self.company.account_opening_move_id = False
        manager = self.env["res.users"].create(
            {
                "name": "Accounting Manager",
                "login": "balance_import_manager",
                "group_ids": [(6, 0, [self.env.ref("account.group_account_manager").id])],
                "company_id": self.company.id,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )

        self._save_opening(self.account_1.with_user(manager), {"opening_balance": 500.0})

        self.assertEqual(self._opening_lines(self.account_1).balance, 500.0)

    def _import_balances(self, import_wizard, dryrun=False):
        preview = import_wizard.parse_preview({"has_headers": True, "quoting": '"'})
        # The columns the import screen maps by itself: an unmatched one is not imported.
        fields = ["/".join(preview["matches"].get(index, [])) for index in range(len(preview["headers"]))]
        result = import_wizard.with_context(account_balance_import=True).execute_import(
            fields, preview["headers"], preview["options"], dryrun=dryrun
        )
        self.env.invalidate_all()
        return result

    def test_new_accounts_are_announced_before_being_created(self):
        """Given a balances file from the guide with an existing account (TEST001) and a code
        that does not exist (TEST999, e.g. mistyped):
        - importing it straight away imports nothing and lists only the new account;
        - the test run lists the new account without creating it;
        - importing after that notice creates the account and loads every balance."""
        file_values = {
            "res_model": "account.account",
            "file": BinaryBytes(
                b"code,name,opening_balance\nTEST001,Test Account 1,100\nTEST999,Mistyped Account,50\n"
            ),
            "file_type": "text/csv",
        }
        new_account_domain = [("code", "=", "TEST999")]

        with self.subTest("importing straight away imports nothing and lists only the new account"):
            held = self._import_balances(self.env["base_import.import"].create(file_values))
            self.assertFalse(held["ids"])
            self.assertIn("TEST999", held["messages"][0]["message"])
            self.assertNotIn("TEST001", held["messages"][0]["message"])
            self.assertFalse(self.env["account.account"].search(new_account_domain))
            self.assertFalse(self._opening_lines(self.account_1))

        import_wizard = self.env["base_import.import"].create(file_values)
        with self.subTest("the test run lists the new account without creating it"):
            test_run = self._import_balances(import_wizard, dryrun=True)
            self.assertEqual(test_run["messages"][0]["type"], "warning")
            self.assertIn("TEST999", test_run["messages"][0]["message"])
            self.assertFalse(self.env["account.account"].search(new_account_domain))

        with self.subTest("importing after the notice creates the account and loads the balances"):
            done = self._import_balances(import_wizard)
            self.assertEqual(len(done["ids"]), 2)
            self.assertTrue(self.env["account.account"].search(new_account_domain))
            self.assertEqual(self._opening_lines(self.account_1).balance, 100.0)
            move = self.company.account_opening_move_id
            self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_accounts_are_matched_by_id_and_renames_are_announced(self):
        """Given a balances file that points an account by its id with another code and name,
        and another row without id that has the code of an existing account:
        - the test run lists the rename and changes nothing;
        - importing straight away imports nothing;
        - importing after the notice renames the account and loads both balances;
        - the row without id is loaded on the account that has its code, not as a new one."""
        csv = (
            ".id,code,name,opening_balance\n"
            f"{self.account_1.id},TEST101,Renamed Account,100\n"
            f",{self.account_2.code},{self.account_2.name},50\n"
        ).encode()
        file_values = {
            "res_model": "account.account",
            "file": BinaryBytes(csv),
            "file_type": "text/csv",
        }
        old_code, old_name = self.account_1.code, self.account_1.name
        account_count = self.env["account.account"].search_count([])

        with self.subTest("importing straight away imports nothing"):
            held = self._import_balances(self.env["base_import.import"].create(file_values))
            self.assertFalse(held["ids"])
            self.assertIn("renamed accounts", held["messages"][0]["message"])
            self.assertIn(f"{old_code} {old_name}", held["messages"][0]["message"])
            self.assertNotIn(self.account_2.name, held["messages"][0]["message"])
            self.assertEqual(self.account_1.code, old_code)
            self.assertFalse(self._opening_lines(self.account_1))

        import_wizard = self.env["base_import.import"].create(file_values)
        with self.subTest("the test run lists the rename without applying it"):
            test_run = self._import_balances(import_wizard, dryrun=True)
            self.assertEqual(test_run["messages"][0]["type"], "warning")
            self.assertEqual(self.account_1.name, old_name)

        with self.subTest("importing after the notice renames and loads the balances"):
            done = self._import_balances(import_wizard)
            self.assertEqual(len(done["ids"]), 2)
            self.assertEqual(self.account_1.name, "Renamed Account")
            self.assertEqual(self.account_1.code, "TEST101")
            self.assertEqual(self._opening_lines(self.account_1).balance, 100.0)
            self.assertEqual(self._opening_lines(self.account_2).balance, 50.0)
            self.assertEqual(self.env["account.account"].search_count([]), account_count)

    def test_account_without_code_is_matched_by_id(self):
        """Given an account without code and a file like the template, that points it by its id
        with the code empty, plus two new accounts, one of them without code (a new account
        without code takes its type from the file, there is no code to derive it from):
        - the row with id loads the balance on that account, without creating another one;
        - the new accounts are announced, with and without code, and then created."""
        no_code = self.env["account.account"].create(
            {"name": "No Code Account", "account_type": "asset_current", "company_ids": [self.company.id]}
        )
        csv = (
            ".id,code,name,account_type,opening_balance\n"
            f"{no_code.id},,No Code Account,asset_current,100\n"
            ",,New Without Code,asset_current,10\n"
            ",TEST998,New With Code,asset_current,-110\n"
        ).encode()
        import_wizard = self.env["base_import.import"].create(
            {"res_model": "account.account", "file": BinaryBytes(csv), "file_type": "text/csv"}
        )

        test_run = self._import_balances(import_wizard, dryrun=True)
        message = test_run["messages"][0]["message"]
        self.assertIn("New Without Code", message)
        self.assertIn("TEST998", message)
        self.assertNotIn("No Code Account", message)

        done = self._import_balances(import_wizard)
        self.assertEqual(len(done["ids"]), 3)
        self.assertFalse(no_code.code)
        self.assertEqual(self._opening_lines(no_code).balance, 100.0)
        self.assertFalse(self.env["account.account"].search([("code", "=ilike", "false")]))

    def _generate_partner_balance_excel(self):
        """Generate Excel file with test partner balance data"""
        # According to wizard code, fields are: name, reference, amount, due_date, currency, amount_company_currency
        data = {
            "Nombre / CUIT / Referencia Interna": [
                "Test Partner 1",
                "Test Partner 2",
                "Test Partner 3",
                "Test Partner 4",
                "Test Partner 5",
            ],
            "Referencia": [
                "Reference 1",
                "Reference 2",
                "Reference 3",
                "Reference 4",
                "Reference 5",
            ],
            "Importe": [1000, 2000, 3000, -2000, -4000],
            "Fecha de Vencimiento (Opcional)": [
                datetime.date(2025, 1, 5),
                datetime.date(2025, 1, 6),
                datetime.date(2025, 1, 7),
                datetime.date(2025, 1, 8),
                datetime.date(2025, 1, 9),
            ],
            "Otra Moneda (Opcional)": ["ARS", "ARS", "ARS", "ARS", "ARS"],
            "Importe en Otra moneda (Opcional)": [1000000, 2000000, 3000000, -2000000, -4000000],
        }

        return BinaryBytes(generate_xlsx(data))

    def test_partner_is_located_by_every_supported_identifier(self):
        """The first column of the template accepts several identifiers.

        Every one of them must resolve to the same partner, including the internal
        code when `partner_internal_code` is installed: it is a different field than
        the internal reference and used to be ignored, so those rows failed with
        "No partner was found for the entered text" even though the partner existed.
        """
        partner = self.partner_1
        partner.ref = "REF-001"
        identifiers = [partner.name, partner.ref]
        if "internal_code" in self.env["res.partner"]._fields:
            partner.internal_code = "IC-001"
            identifiers.append(partner.internal_code)

        wizard = self.env["account.balance_import_wizard"]
        for identifier in identifiers:
            found = self.env["res.partner"].search(wizard._get_partner_domain(identifier))
            self.assertEqual(found, partner, f"The partner should be located by '{identifier}'")

    def test_partner_balance_import_basic(self):
        """
        Basic partner balance import test

        This test validates:
        1. Wizard creation with Excel file
        2. Correct import of 5 partners with different amounts
        3. Generation of corresponding account moves
        4. Partners have balances in their receivable accounts
        5. Moves are properly posted
        """

        # Generate test Excel file
        excel_file = self._generate_partner_balance_excel()

        # Create import wizard
        wizard = self.env["account.balance_import_wizard"].create(
            {
                "company_id": self.company.id,
                "mode": "partner_balance",
                "partner_balance_type": "receivable",
                "journal_id": self.journal.id,
                "counterpart_account_id": self.counterpart_account.id,
                "accounting_date": datetime.date(2025, 1, 1),
                "file": excel_file,
            }
        )

        # Execute import
        result = wizard.action_import()

        # Validate result is a window action
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "account.move")

        # Get generated moves
        generated_moves = self.env["account.move"].browse(result["domain"][0][2])

        # Validate 5 moves were generated (one per partner)
        self.assertEqual(len(generated_moves), 5, "Should have created 5 account moves")

        # Validate all moves are posted
        for move in generated_moves:
            self.assertEqual(move.state, "posted", f"Move {move.name} should be posted")

        # Validate amounts for each move
        expected_amounts = [
            ("Reference 1", 1000.0),
            ("Reference 2", 2000.0),
            ("Reference 3", 3000.0),
            ("Reference 4", 2000.0),  # absolute value
            ("Reference 5", 4000.0),  # absolute value
        ]

        for ref, expected_amount in expected_amounts:
            move = generated_moves.filtered(lambda m: m.ref == ref)
            self.assertEqual(len(move), 1, f"Should have exactly one move with reference {ref}")

            # Each move should have 2 lines (one for partner and one for counterpart)
            self.assertEqual(len(move.line_ids), 2, f"Move {move.name} should have 2 lines")

            # Verify move is balanced (debit = credit)
            total_debit = sum(move.line_ids.mapped("debit"))
            total_credit = sum(move.line_ids.mapped("credit"))
            self.assertEqual(total_debit, total_credit, f"Move {move.name} must be balanced")
            self.assertAlmostEqual(
                total_debit,
                expected_amount,
                places=2,
                msg=f"Total amount for move {move.name} should be {expected_amount}",
            )

        # Validate partner lines have correct partner_id
        partner_line_1 = generated_moves.filtered(lambda m: m.ref == "Reference 1").line_ids.filtered(
            lambda l: l.partner_id
        )
        self.assertEqual(partner_line_1.partner_id, self.partner_1, "Line should have partner 1")

        # Validate debit amounts (positive)
        moves_with_debit_partner = generated_moves.filtered(
            lambda m: m.ref in ["Reference 1", "Reference 2", "Reference 3"]
        )
        for move in moves_with_debit_partner:
            partner_lines = move.line_ids.filtered(lambda l: l.partner_id)
            # Find line with debit (partner receivable account)
            debit_line = partner_lines.filtered(lambda l: l.debit > 0)
            self.assertEqual(len(debit_line), 1, f"Should have exactly one debit line in {move.name}")
            self.assertEqual(debit_line.credit, 0.0, f"Debit line in {move.name} should not have credit")

        moves_with_credit_partner = generated_moves.filtered(lambda m: m.ref in ["Reference 4", "Reference 5"])
        for move in moves_with_credit_partner:
            partner_lines = move.line_ids.filtered(lambda l: l.partner_id)
            # Find line with credit (partner payable account)
            credit_line = partner_lines.filtered(lambda l: l.credit > 0)
            self.assertEqual(len(credit_line), 1, f"Should have exactly one credit line in {move.name}")
            self.assertEqual(credit_line.debit, 0.0, f"Credit line in {move.name} should not have debit")

        # Validate due dates
        move_ref_1 = generated_moves.filtered(lambda m: m.ref == "Reference 1")
        # Find debit line (receivable account) which has the due date
        receivable_line = move_ref_1.line_ids.filtered(lambda l: l.partner_id and l.debit > 0)
        self.assertEqual(len(receivable_line), 1, "Should have exactly one receivable line")
        self.assertEqual(
            receivable_line.date_maturity,
            datetime.date(2025, 1, 5),
            "First line due date should be 01/05/25",
        )

        # Validate correct journal was used
        self.assertTrue(
            all(move.journal_id == self.journal for move in generated_moves),
            "All moves should use the test journal",
        )

        # Validate correct accounting date was used
        self.assertTrue(
            all(move.date == datetime.date(2025, 1, 1) for move in generated_moves),
            "All moves should have accounting date 01/01/25",
        )

    def test_partner_balance_import_unsupported_format_raises_readable_error(self):
        """A file that is neither XLS nor XLSX (e.g. a CSV) must raise a readable error."""
        wizard = self.env["account.balance_import_wizard"].create(
            {
                "company_id": self.company.id,
                "mode": "partner_balance",
                "partner_balance_type": "receivable",
                "journal_id": self.journal.id,
                "counterpart_account_id": self.counterpart_account.id,
                "accounting_date": datetime.date(2025, 1, 1),
                "file": BinaryBytes(b"Nombre / CUIT,Referencia,Importe\r\nPartner,DOC-1,100"),
            }
        )
        with self.assertRaisesRegex(ValidationError, r"\.xls or \.xlsx"):
            wizard.action_import()

    def test_partner_balance_import_adjust_reconcile(self):
        """
        Test adjust import with auto-reconciliation
        """
        # Create an initial entry (debt) for partner 1
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.journal.id,
                "date": "2025-01-01",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Initial Debt",
                            "partner_id": self.partner_1.id,
                            "account_id": self.partner_1.property_account_receivable_id.id,
                            "debit": 1000.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Counterpart",
                            "account_id": self.counterpart_account.id,
                            "debit": 0.0,
                            "credit": 1000.0,
                        },
                    ),
                ],
            }
        )
        entry._post()

        # Import an adjustment to set balance to 600
        # Difference will be -400 (credit)
        data = {
            "Nombre / CUIT / Referencia Interna": [self.partner_1.name],
            "Referencia": ["Adjustment 1"],
            "Importe": [600.0],
        }
        excel_file = BinaryBytes(generate_xlsx(data))

        wizard = self.env["account.balance_import_wizard"].create(
            {
                "company_id": self.company.id,
                "mode": "partner_balance",
                "partner_balance_type": "receivable",
                "journal_id": self.journal.id,
                "counterpart_account_id": self.counterpart_account.id,
                "accounting_date": datetime.date(2025, 1, 10),
                "file": excel_file,
                "import_type": "adjust",
                "reconcile_debt": True,
            }
        )

        wizard.action_import()

        # Check the line residual
        debt_line = entry.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
        self.assertEqual(debt_line.amount_residual, 600.0, "The debt should be reduced to 600")
