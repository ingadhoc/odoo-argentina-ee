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
class TestAccountBalanceImportChecks(TransactionCase):
    """Test cases for account balance import checks functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up company
        cls.company = cls.env.company

        # Get or create counterpart account (unaffected earnings)
        cls.counterpart_account = cls.company.get_unaffected_earnings_account()

        # Create test partners
        cls.partners = cls.env["res.partner"].create(
            [{"name": f"Test Partner {i}", "company_id": cls.company.id} for i in range(1, 5)]
        )
        cls.partner_1, cls.partner_2, cls.partner_3, cls.partner_4 = cls.partners

        # Create bank for own checks test
        cls.bank = cls.env["res.bank"].create(
            {
                "name": "Test Bank",
            }
        )

        # Create outstanding account for bank journal
        cls.outstanding_account_bank = cls.env["account.account"].create(
            {
                "code": "TESTOUT01",
                "name": "Outstanding Bank Account",
                "account_type": "asset_current",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

        # Create bank journal for own checks
        cls.bank_journal = cls.env["account.journal"].create(
            {
                "name": "Test Bank Journal",
                "code": "TBJ",
                "type": "bank",
                "company_id": cls.company.id,
                "bank_id": cls.bank.id,
                "default_account_id": cls.outstanding_account_bank.id,
            }
        )

        # Configure payment method line for own checks (outbound own_checks)
        cls.own_check_method = cls.env["account.payment.method"].search(
            [("code", "=", "own_checks"), ("payment_type", "=", "outbound")], limit=1
        )
        if cls.own_check_method:
            # Check if payment method line already exists
            existing_line = cls.bank_journal.outbound_payment_method_line_ids.filtered(
                lambda l: l.payment_method_id == cls.own_check_method
            )
            if not existing_line:
                cls.env["account.payment.method.line"].create(
                    {
                        "name": cls.own_check_method.name,
                        "payment_method_id": cls.own_check_method.id,
                        "journal_id": cls.bank_journal.id,
                        "payment_account_id": cls.outstanding_account_bank.id,
                    }
                )

        # Create outstanding account for cash journal
        cls.outstanding_account_cash = cls.env["account.account"].create(
            {
                "code": "TESTOUT02",
                "name": "Outstanding Cash Account",
                "account_type": "asset_current",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

        # Create cash journal for third party checks
        cls.cash_journal = cls.env["account.journal"].create(
            {
                "name": "Test Cash Journal",
                "code": "TCJ",
                "type": "cash",
                "company_id": cls.company.id,
                "default_account_id": cls.outstanding_account_cash.id,
            }
        )

        # Configure payment method line for third party checks (inbound new_third_party_checks)
        cls.third_check_method = cls.env["account.payment.method"].search(
            [("code", "=", "new_third_party_checks"), ("payment_type", "=", "inbound")], limit=1
        )
        if cls.third_check_method:
            # Check if payment method line already exists
            existing_line = cls.cash_journal.inbound_payment_method_line_ids.filtered(
                lambda l: l.payment_method_id == cls.third_check_method
            )
            if not existing_line:
                cls.env["account.payment.method.line"].create(
                    {
                        "name": cls.third_check_method.name,
                        "payment_method_id": cls.third_check_method.id,
                        "journal_id": cls.cash_journal.id,
                        "payment_account_id": cls.outstanding_account_cash.id,
                    }
                )

    def _generate_check_balance_excel(self, check_type="issue_check"):
        """Generate Excel file with test check data"""
        if check_type == "issue_check":
            # Own checks
            data = {
                "Número": [12345, 67890],
                "Importe": [10000, 15000],
                "Fecha de Pago": [datetime.date(2025, 2, 1), datetime.date(2025, 2, 15)],
                "Nombre / CUIT / Referencia Interna": ["Test Partner 1", "Test Partner 2"],
                "Otra Moneda (Opcional)": ["", ""],
                "Importe en Otra moneda (Opcional)": ["", ""],
            }
        else:
            # Third party checks
            data = {
                "Número": [11111, 22222],
                "Importe": [8000, 12000],
                "Fecha de Pago": [datetime.date(2025, 2, 10), datetime.date(2025, 2, 20)],
                "Nombre / CUIT / Referencia Interna": ["Test Partner 3", "Test Partner 4"],
                "CUIT del Librador": ["20123456789", "20987654321"],
                "Otra Moneda (Opcional)": ["", ""],
                "Importe en Otra moneda (Opcional)": ["", ""],
                "Banco": ["Test Bank", "Test Bank"],
            }

        return base64.b64encode(generate_xls(data))

    def test_check_balance_import_own_checks(self):
        """
        Own checks import test

        This test validates:
        1. La creación del wizard con el archivo Excel de cheques propios
        2. La importación correcta de cheques propios
        3. La generación de pagos (account.payment) correspondientes
        4. Que los pagos están posteados correctamente
        5. Que los cheques tienen los datos correctos
        """

        # Generar archivo Excel de prueba para cheques propios
        excel_file = self._generate_check_balance_excel(check_type="issue_check")

        # Crear el wizard de importación
        wizard = self.env["account.balance_import_wizard"].create(
            {
                "company_id": self.company.id,
                "mode": "check_balance",
                "check_type": "issue_check",
                "journal_id": self.bank_journal.id,
                "counterpart_account_id": self.counterpart_account.id,
                "accounting_date": datetime.date(2025, 1, 1),
                "file": excel_file,
            }
        )

        # Ejecutar la importación
        result = wizard.action_import()

        # Validar que el resultado es una acción de ventana
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "account.payment")

        # Obtener los pagos generados
        payment_ids = result.get("res_id") or result.get("domain")[0][2]
        generated_payments = self.env["account.payment"].browse(payment_ids)

        # Validar que se generaron 2 pagos
        self.assertEqual(len(generated_payments), 2, "Deberían haberse creado 2 pagos")

        # Validar que todos los pagos están en estado in_process o posted
        # Los cheques propios pueden quedar en in_process esperando ser impresos/confirmados
        self.assertTrue(
            all(payment.state in ["in_process", "posted"] for payment in generated_payments),
            "Todos los pagos deberían estar en in_process o posted",
        )

        # Validar que son pagos de tipo outbound (salientes)
        self.assertTrue(
            all(payment.payment_type == "outbound" for payment in generated_payments),
            "Todos los cheques propios deberían ser pagos outbound",
        )

        # Validar que tienen partner_type supplier
        self.assertTrue(
            all(payment.partner_type == "supplier" for payment in generated_payments),
            "Todos los cheques propios deberían tener partner_type supplier",
        )

        # Validar que se usó el diario correcto
        self.assertTrue(
            all(payment.journal_id == self.bank_journal for payment in generated_payments),
            "Todos los pagos deberían usar el diario de banco",
        )

        # Validar que se usó la fecha contable correcta
        self.assertTrue(
            all(payment.date == datetime.date(2025, 1, 1) for payment in generated_payments),
            "Todos los pagos deberían tener la fecha 01/01/25",
        )

        # Validar que tienen cheques asociados
        payment_1 = generated_payments.filtered(lambda p: p.partner_id == self.partner_1)
        self.assertEqual(len(payment_1), 1, "Debería haber un pago para el partner 1")
        self.assertEqual(len(payment_1.l10n_latam_new_check_ids), 1, "El pago debería tener exactamente un cheque")

        # Validate check number
        check_1 = payment_1.l10n_latam_new_check_ids[0]
        self.assertEqual(check_1.name, "12345", "Check number should be 12345")
        self.assertEqual(check_1.amount, 10000.0, "Check amount should be 10000")
        self.assertEqual(check_1.payment_date, datetime.date(2025, 2, 1), "Check payment date should be 02/01/25")

    def test_check_balance_import_third_checks(self):
        """
        Third party checks import test

        This test validates:
        1. Wizard creation with third party checks Excel file
        2. Correct import of third party checks
        3. Generation of corresponding payments (account.payment)
        4. Payments are in correct state
        5. Checks have correct data
        """

        # Generate test Excel file for third party checks
        excel_file = self._generate_check_balance_excel(check_type="third_check")

        # Create import wizard
        wizard = self.env["account.balance_import_wizard"].create(
            {
                "company_id": self.company.id,
                "mode": "check_balance",
                "check_type": "third_check",
                "journal_id": self.cash_journal.id,
                "counterpart_account_id": self.counterpart_account.id,
                "accounting_date": datetime.date(2025, 1, 1),
                "file": excel_file,
            }
        )

        # Execute import
        result = wizard.action_import()

        # Validate result is a window action
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "account.payment")

        # Get generated payments
        payment_ids = result.get("res_id") or result.get("domain")[0][2]
        generated_payments = self.env["account.payment"].browse(payment_ids)

        # Validate 2 payments were generated
        self.assertEqual(len(generated_payments), 2, "Should have created 2 payments")

        # Validate all payments are in in_process or posted state
        self.assertTrue(
            all(payment.state in ["in_process", "posted"] for payment in generated_payments),
            "All payments should be in in_process or posted state",
        )

        # Validate payments are inbound type
        self.assertTrue(
            all(payment.payment_type == "inbound" for payment in generated_payments),
            "All third party checks should be inbound payments",
        )

        # Validate payments have customer partner_type
        self.assertTrue(
            all(payment.partner_type == "customer" for payment in generated_payments),
            "All third party checks should have customer partner_type",
        )

        # Validate correct journal was used
        self.assertTrue(
            all(payment.journal_id == self.cash_journal for payment in generated_payments),
            "All payments should use the cash journal",
        )

        # Validate correct accounting date was used
        self.assertTrue(
            all(payment.date == datetime.date(2025, 1, 1) for payment in generated_payments),
            "All payments should have date 01/01/25",
        )

        # Validate payments have associated checks
        payment_3 = generated_payments.filtered(lambda p: p.partner_id == self.partner_3)
        self.assertEqual(len(payment_3), 1, "Should have one payment for partner 3")
        self.assertEqual(len(payment_3.l10n_latam_new_check_ids), 1, "Payment should have exactly one check")

        # Validate check number
        check_3 = payment_3.l10n_latam_new_check_ids[0]
        self.assertEqual(check_3.name, "11111", "Check number should be 11111")
        self.assertEqual(check_3.amount, 8000.0, "Check amount should be 8000")
        self.assertEqual(check_3.payment_date, datetime.date(2025, 2, 10), "Check payment date should be 02/10/25")
        self.assertEqual(check_3.bank_id, self.bank, "Check bank should be Test Bank")
