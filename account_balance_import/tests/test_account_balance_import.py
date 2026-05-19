import base64
import datetime
import io

import xlwt
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


def generate_xls(data):
    """
    Generates an XLS file from the given data dictionary. Each key in the `data` dictionary represents a column header,
    and its corresponding values are written as rows under that column.

    Date and datetime objects in the values will automatically set the style of the cell to a date/datetime.

    :param dict data: keys are column headers, values are rows.
    :return bytes: the xls file as bytes.
    """
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Sheet1")

    default_style = xlwt.XFStyle()

    date_style = xlwt.XFStyle()
    date_style.num_format_str = "yyyy-mm-dd"

    datetime_style = xlwt.XFStyle()
    datetime_style.num_format_str = "yyyy-mm-dd hh:mm:ss"

    for column, (key, values) in enumerate(data.items()):
        ws.write(0, column, key, default_style)
        for row, value in enumerate(values, 1):
            style = default_style
            if isinstance(value, datetime.datetime):
                style = datetime_style
            elif isinstance(value, datetime.date):
                style = date_style
            ws.write(row, column, value, style)

    output = io.BytesIO()
    wb.save(output)
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

        return base64.b64encode(generate_xls(data))

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
        excel_file = base64.b64encode(generate_xls(data))

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
