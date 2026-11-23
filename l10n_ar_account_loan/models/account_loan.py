from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from odoo.tools.misc import format_date


class AccountLoan(models.Model):
    _inherit = "account.loan"

    is_ar_loan = fields.Boolean(
        string="Argentinian Loan",
        default=lambda self: self.env.company.account_fiscal_country_id.code == "AR",
        help="Enable the Argentinian flow: register the disbursement, generate a "
        "supplier bill per instalment (with taxes) and cancel everything with a "
        "standard payment against the bank contact. Disables the native monthly entries.",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Bank Contact",
        help="Dedicated contact (e.g. 'Bank X - LOAN'). Its payable account ('Loans payable') "
        "is where both the capital and the interest bills post, so a standard payment "
        "reconciles them together. The capital account is taken from this contact.",
    )
    bank_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Bank Journal",
        domain="[('type', 'in', ('bank', 'cash'))]",
        help="Journal used for the disbursement; its liquidity account receives the credited amount.",
    )
    loan_payable_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Loan Payable Account",
        compute="_compute_loan_payable_account",
        store=True,
        readonly=False,
        domain="[('account_type', '=', 'liability_payable'), ('reconcile', '=', True)]",
        help="Payable account where the capital posts. Defaults to the bank contact's payable "
        "account and must match it, so capital and interest bills reconcile together.",
    )
    interest_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Interest Account",
        domain="[('account_type', 'in', ('expense', 'expense_depreciation', 'expense_other'))]",
    )
    interest_tax_ids = fields.Many2many(
        comodel_name="account.tax",
        string="Interest Taxes",
        domain="[('type_tax_use', '=', 'purchase')]",
        help="Default taxes (VAT) pre-loaded on the interest line of each bill.",
    )
    disbursement_move_id = fields.Many2one(
        comodel_name="account.move",
        string="Disbursement Entry",
        readonly=True,
        copy=False,
    )
    invoice_count = fields.Integer(compute="_compute_invoice_count")

    @api.depends("partner_id", "company_id")
    def _compute_loan_payable_account(self):
        """Default to the bank contact's payable account (editable). Keeping this as the
        default is what stops the payable-match constraint from tripping in the normal flow."""
        for loan in self:
            loan.loan_payable_account_id = loan.partner_id.with_company(loan.company_id).property_account_payable_id

    @api.depends("line_ids.invoice_id")
    def _compute_invoice_count(self):
        for loan in self:
            loan.invoice_count = len(loan.line_ids.invoice_id)

    @api.depends(
        "amount_borrowed",
        "line_ids.principal",
        "state",
        "line_ids.is_payment_move_posted",
        "line_ids.capital_reconciled",
    )
    def _compute_outstanding_balance(self):
        """For AR loans the balance drops as each instalment's capital gets reconciled
        (the native flow keys off ``is_payment_move_posted``, which AR moves never set)."""
        ar_loans = self.filtered("is_ar_loan")
        super(AccountLoan, self - ar_loans)._compute_outstanding_balance()
        for loan in ar_loans:
            balance = loan.amount_borrowed
            if loan.state == "running":
                balance -= sum(loan.line_ids.filtered("capital_reconciled").mapped("principal"))
            loan.outstanding_balance = balance

    @api.constrains("is_ar_loan", "partner_id", "loan_payable_account_id", "company_id")
    def _check_ar_payable_match(self):
        """Capital and interest bills only reconcile together with one payment if they land
        in the same payable account for the same partner. The bills always use the contact's
        payable account, so the loan payable account must match it. The compute defaults it
        correctly; this guards against a manual override that would silently break reconciliation."""
        for loan in self.filtered("is_ar_loan"):
            if not loan.partner_id or not loan.loan_payable_account_id:
                continue
            partner_payable = loan.partner_id.with_company(loan.company_id).property_account_payable_id
            if partner_payable != loan.loan_payable_account_id:
                raise ValidationError(
                    _(
                        "The loan payable account (%(loan_account)s) must match the bank contact's "
                        "payable account (%(partner_account)s) so capital and bills reconcile together.",
                        loan_account=loan.loan_payable_account_id.display_name,
                        partner_account=partner_payable.display_name or "-",
                    )
                )

    # -------------------------------------------------------------------------
    # Confirm
    # -------------------------------------------------------------------------
    def action_confirm(self):
        """AR loans skip the native monthly entries; they only validate the
        schedule and move to running. Money is registered later through the
        disbursement + per-instalment bills + standard payment."""
        ar_loans = self.filtered("is_ar_loan")
        standard_loans = self - ar_loans
        if standard_loans:
            super(AccountLoan, standard_loans).action_confirm()
        for loan in ar_loans:
            loan._check_ar_schedule()
            loan.state = "running"
        return True

    def _check_ar_schedule(self):
        """Reuse the native schedule validations without requiring the LT/ST/expense accounts.

        Native couples these checks with the account/journal checks and the monthly
        entry generation inside ``action_confirm`` (no extractable hook), so we mirror
        only the schedule half here. Keep in sync with ``account_loans`` action_confirm.
        """
        self.ensure_one()
        rounding = self.currency_id.rounding
        if not self.name:
            raise UserError(_("The loan name should be set."))
        if self.is_wrong_date:
            raise UserError(_("The loan date should be earlier than the loan lines date."))
        if float_compare(self.amount_borrowed_difference, 0.0, precision_rounding=rounding) != 0:
            raise UserError(
                _(
                    "The loan amount %(loan_amount)s should be equal to the sum of the principals.",
                    loan_amount=self.currency_id.format(self.amount_borrowed),
                )
            )
        if float_compare(self.interest_difference, 0.0, precision_rounding=rounding) != 0:
            raise UserError(_("The loan interest should be equal to the sum of the loan lines interest."))
        if self.duration_difference != 0:
            raise UserError(_("The loan duration should be equal to the number of loan lines."))

    def _check_ar_config(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Set the bank contact on the loan."))
        if not self.bank_journal_id:
            raise UserError(_("Set the bank journal used for the disbursement."))
        if not self.loan_payable_account_id:
            raise UserError(
                _(
                    "Set the loan payable account. It defaults to the bank contact's payable "
                    "account — the contact '%s' has none set, so configure it there or pick one here.",
                    self.partner_id.display_name,
                )
            )
        if not self.bank_journal_id.default_account_id:
            raise UserError(_("The bank journal %s has no liquidity account.", self.bank_journal_id.display_name))

    # -------------------------------------------------------------------------
    # US1 - Disbursement
    # -------------------------------------------------------------------------
    def action_register_disbursement(self):
        self.ensure_one()
        if self.disbursement_move_id:
            raise UserError(_("The disbursement was already registered."))
        self._check_ar_schedule()
        self._check_ar_config()

        payable_account = self.loan_payable_account_id
        capital_lines = self.line_ids.filtered(lambda l: not l.is_grace_period)
        if self.skip_until_date:
            # Mirror native: periods already booked by hand are not re-recorded.
            capital_lines = capital_lines.filtered(lambda l: l.date >= self.skip_until_date)
        disbursed_amount = sum(capital_lines.mapped("principal"))
        line_commands = [
            Command.create(
                {
                    "account_id": self.bank_journal_id.default_account_id.id,
                    "debit": disbursed_amount,
                    "name": _("Loan disbursement - %s", self.name),
                }
            ),
            *(
                Command.create(
                    {
                        "account_id": payable_account.id,
                        "partner_id": self.partner_id.id,
                        "credit": line.principal,
                        "date_maturity": line.date,
                        "name": _(
                            "%(loan)s - Capital %(date)s",
                            loan=self.name,
                            date=format_date(self.env, line.date, date_format="MM/y"),
                        ),
                    }
                )
                for line in capital_lines
            ),
        ]
        move = (
            self.env["account.move"]
            .with_company(self.company_id)
            .create(
                {
                    "move_type": "entry",
                    "company_id": self.company_id.id,
                    "journal_id": self.bank_journal_id.id,
                    "date": self.date,
                    "ref": _("Loan disbursement - %s", self.name),
                    "line_ids": line_commands,
                }
            )
        )
        move.action_post()

        # Match each instalment to its capital line by maturity date (each schedule
        # line has a distinct date) rather than by position in the recordset.
        amls_by_date = {aml.date_maturity: aml for aml in move.line_ids if aml.account_id == payable_account}
        for line in capital_lines:
            line.capital_move_line_id = amls_by_date.get(line.date)
        self.disbursement_move_id = move
        return self.action_open_disbursement()

    # -------------------------------------------------------------------------
    # Smart buttons
    # -------------------------------------------------------------------------
    def action_open_disbursement(self):
        self.ensure_one()
        return self.disbursement_move_id._get_records_action(name=_("Disbursement Entry"))

    def action_open_invoices(self):
        self.ensure_one()
        return self.line_ids.invoice_id._get_records_action(name=_("Loan Bills"))

    # -------------------------------------------------------------------------
    # Teardown — the AR moves link via disbursement_move_id / line.invoice_id,
    # not the native generating_loan_line_id, so the native cancel/draft/unlink
    # (which only touch line_ids.generated_move_ids) would leave them orphaned.
    # -------------------------------------------------------------------------
    def _ar_teardown_moves(self):
        for loan in self.filtered("is_ar_loan"):
            moves = loan.disbursement_move_id | loan.line_ids.invoice_id
            moves.filtered(lambda m: m.state != "cancel")._unlink_or_reverse()
            loan.disbursement_move_id = False
            loan.line_ids.write({"capital_move_line_id": False, "invoice_id": False})

    def action_cancel(self):
        self._ar_teardown_moves()
        return super().action_cancel()

    def action_set_to_draft(self):
        self._ar_teardown_moves()
        return super().action_set_to_draft()

    @api.ondelete(at_uninstall=False)
    def _unlink_ar_loan(self):
        for loan in self.filtered("is_ar_loan"):
            (loan.disbursement_move_id | loan.line_ids.invoice_id).filtered(
                lambda m: m.state != "cancel"
            )._unlink_or_reverse()
