import io

from odoo.tests import HttpCase, tagged
from openpyxl import load_workbook


@tagged("post_install", "-at_install")
class TestAccountBalanceXls(HttpCase):
    def test_template_lists_the_chart_with_ids(self):
        self.authenticate("admin", "admin")
        company = self.env.company
        expense = self.env["account.account"].create(
            {"code": "XLS001", "name": "XLS expense", "account_type": "expense", "company_ids": [company.id]}
        )
        payable = self.env["account.account"].create(
            {"code": "XLS002", "name": "XLS payable", "account_type": "liability_payable", "company_ids": [company.id]}
        )

        response = self.url_open("/account_balance_import/account_balance_xls")

        self.assertEqual(response.status_code, 200)
        rows = list(load_workbook(io.BytesIO(response.content)).active.iter_rows(values_only=True))
        self.assertEqual(rows[0][:4], (".id", "code", "name", "opening_balance"))
        ids = {row[0] for row in rows[1:]}
        self.assertIn(expense.id, ids)
        self.assertNotIn(payable.id, ids)
