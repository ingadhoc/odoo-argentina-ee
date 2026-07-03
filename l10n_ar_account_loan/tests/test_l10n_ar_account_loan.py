from dateutil.relativedelta import relativedelta
from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestArAccountLoan(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payable_account = cls.company_data["default_account_payable"]  # liability_payable, reconcile
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.interest_account = cls.company_data["default_account_expense"]
        cls.tax_purchase = cls.company_data["default_tax_purchase"]
        cls.bank_partner = cls.env["res.partner"].create(
            {
                "name": "Bank X - LOAN",
                "property_account_payable_id": cls.payable_account.id,
            }
        )
        # 3 capital instalments (400 each) + 1 grace instalment (principal 0, interest 50)
        date = "2024-01-01"
        cls.loan = cls.env["account.loan"].create(
            {
                "name": "Prestamo ARG",
                "date": date,
                "duration": 4,
                "amount_borrowed": 1200,
                "interest": 350,
                "is_ar_loan": True,
                "partner_id": cls.bank_partner.id,
                "bank_journal_id": cls.bank_journal.id,
                "interest_account_id": cls.interest_account.id,
                "interest_tax_ids": [Command.set(cls.tax_purchase.ids)],
                "line_ids": [
                    Command.create(
                        {
                            "date": fields.Date.to_date(date) + relativedelta(months=m),
                            "principal": principal,
                            "interest": 100,
                        }
                    )
                    for m, principal in enumerate([400, 400, 400])
                ]
                + [
                    Command.create(
                        {
                            "date": fields.Date.to_date(date) + relativedelta(months=3),
                            "principal": 0,
                            "interest": 50,
                        }
                    )
                ],
            }
        )

    def test_confirm_skips_native_entries(self):
        self.loan.action_confirm()
        self.assertEqual(self.loan.state, "running")
        self.assertFalse(self.loan.line_ids.generated_move_ids, "AR loans must not create the native monthly entries")

    def test_disbursement(self):
        self.loan.action_confirm()
        self.loan.action_register_disbursement()
        move = self.loan.disbursement_move_id
        self.assertTrue(move)
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.company_id, self.loan.company_id)

        bank_line = move.line_ids.filtered(lambda l: l.account_id == self.bank_journal.default_account_id)
        self.assertEqual(bank_line.debit, 1200, "bank debit equals the credited capital")

        payable_lines = move.line_ids.filtered(lambda l: l.account_id == self.payable_account)
        self.assertEqual(len(payable_lines), 3, "one payable line per capital instalment, grace excluded")
        self.assertEqual(sum(payable_lines.mapped("credit")), 1200)
        self.assertTrue(all(l.partner_id == self.bank_partner for l in payable_lines))

        capital_lines = self.loan.line_ids.filtered(lambda l: l.principal > 0)
        self.assertTrue(all(l.capital_move_line_id for l in capital_lines))
        # each instalment is linked to the payable line with its own maturity date
        self.assertTrue(all(l.capital_move_line_id.date_maturity == l.date for l in capital_lines))
        grace_line = self.loan.line_ids.filtered("is_grace_period")
        self.assertFalse(grace_line.capital_move_line_id, "grace instalment has no capital line")

        with self.assertRaises(UserError):
            self.loan.action_register_disbursement()

    def test_generate_bill(self):
        self.loan.action_confirm()
        line = self.loan.line_ids[0]
        line.action_generate_invoice()
        bill = line.invoice_id
        self.assertEqual(bill.move_type, "in_invoice")
        self.assertEqual(bill.partner_id, self.bank_partner)
        self.assertEqual(bill.amount_untaxed, 100)
        self.assertEqual(bill.company_id, self.loan.company_id)
        with self.assertRaises(UserError):
            line.action_generate_invoice()

    def test_cancel_tears_down_ar_moves(self):
        self.loan.action_confirm()
        self.loan.action_register_disbursement()
        self.loan.line_ids[0].action_generate_invoice()
        disbursement = self.loan.disbursement_move_id

        self.loan.action_cancel()

        self.assertEqual(self.loan.state, "cancelled")
        self.assertFalse(self.loan.disbursement_move_id, "disbursement link cleared on cancel")
        self.assertFalse(self.loan.line_ids.capital_move_line_id)
        self.assertFalse(self.loan.line_ids.invoice_id)
        # disbursement must not survive as an orphaned posted entry: it is either
        # unlinked (deleted) or reversed/cancelled.
        if disbursement.exists():
            self.assertTrue(disbursement.state == "cancel" or disbursement.reversal_move_ids)

    def test_payable_defaults_to_contact(self):
        # the loan payable account defaults (computed-editable) to the bank contact's payable
        self.assertEqual(self.loan.loan_payable_account_id, self.bank_partner.property_account_payable_id)

    def test_payable_mismatch_blocked(self):
        other_payable = self.env["account.account"].create(
            {
                "name": "Other payable",
                "code": "OTHERPAY",
                "account_type": "liability_payable",
                "reconcile": True,
            }
        )
        with self.assertRaises(ValidationError):
            self.loan.loan_payable_account_id = other_payable

    def test_missing_payable_account_raises(self):
        self.loan.loan_payable_account_id = False
        self.loan.action_confirm()
        with self.assertRaises(UserError):
            self.loan.action_register_disbursement()

    def test_close_on_full_capital_reconcile(self):
        self.loan.action_confirm()
        self.loan.action_register_disbursement()
        self.assertEqual(self.loan.outstanding_balance, 1200)
        capital_amls = self.loan.line_ids.capital_move_line_id

        # counterpart entry that cancels the whole capital (same account + partner)
        counterpart = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    Command.create(
                        {
                            "account_id": self.payable_account.id,
                            "partner_id": self.bank_partner.id,
                            "debit": 1200,
                        }
                    ),
                    Command.create(
                        {
                            "account_id": self.bank_journal.default_account_id.id,
                            "credit": 1200,
                        }
                    ),
                ],
            }
        )
        counterpart.action_post()
        counterpart_payable = counterpart.line_ids.filtered(lambda l: l.account_id == self.payable_account)

        (capital_amls + counterpart_payable).reconcile()

        self.assertTrue(all(capital_amls.mapped("reconciled")))
        self.assertEqual(self.loan.state, "closed", "loan closes once all capital is reconciled")
