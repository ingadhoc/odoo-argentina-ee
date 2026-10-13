=================
Argentinian Loans
=================

Register taken loans (disbursement, monthly bills with taxes and standard
payment) the Argentinian way.

This module is a bridge over the Enterprise ``account_loans`` module. It does
not modify it: for loans flagged as Argentinian it replaces the native monthly
journal entries with a bank disbursement, a supplier bill per instalment (with
VAT/perceptions) and a standard payment, so the interest tax credit is captured
and the debt is tracked instalment by instalment using standard Odoo mechanisms.

Características
===============

- Adds an **Argentinian Loan** toggle to each loan (defaulted on when the
  company's fiscal country is Argentina). When enabled, the native monthly
  entries are not generated.
- **Register disbursement** (button on the loan): posts an entry in the bank
  journal — debit the journal's liquidity account for the credited amount, and
  one credit line per instalment on the loan payable account, with the
  instalment's due date and the bank contact.
- **Generate bill** (button per amortization line): creates a supplier bill to
  the bank contact with the interest pre-loaded and the loan's default taxes
  (VAT); perceptions/other charges are completed manually against the real
  document.
- **Standard payment**: capital and interest bills post to the same payable
  account for the same contact, so a single standard payment reconciles them
  together, independently of the bank statement reconciliation.
- **Automatic close**: the loan moves to *Closed* once every instalment's
  capital is fully reconciled; the outstanding balance decreases as the capital
  is reconciled.
- **Grace instalments** (principal = 0): generate no capital line but can still
  be billed for their interest.
- **Teardown**: cancelling, resetting to draft or deleting an Argentinian loan
  reverses or unlinks its disbursement entry and bills, leaving no orphaned
  posted entries.
- Smart buttons for the disbursement entry and the generated bills; the native
  *Posted Entries* button is hidden on Argentinian loans (it does not apply to
  this flow).
- The loan payable account defaults to the bank contact's payable account and
  is validated to match it, so capital and bills always reconcile together.

Detalles Técnicos
=================

**Modelos heredados**

- ``account.loan``

  - Fields: ``is_ar_loan``, ``partner_id`` (bank contact), ``bank_journal_id``,
    ``loan_payable_account_id`` (computed-editable, defaults to the contact's
    payable account), ``interest_account_id``, ``interest_tax_ids``,
    ``disbursement_move_id``, ``is_disbursed`` (computed), ``invoice_count``
    (computed).
  - Overrides ``action_confirm`` (Argentinian loans only validate the schedule
    and move to *running*, skipping the native monthly entries),
    ``action_cancel``, ``action_set_to_draft`` and ``_compute_outstanding_balance``.
  - Adds ``action_register_disbursement``, ``action_open_disbursement`` and
    ``action_open_invoices``.
  - Constraint ``_check_ar_payable_match`` (the loan payable account must match
    the bank contact's payable account) and an ``@api.ondelete`` teardown.

- ``account.loan.line``

  - Fields: ``capital_move_line_id``, ``invoice_id``, ``is_grace_period``
    (stored computed), ``capital_reconciled`` (stored related to the capital
    move line's ``reconciled``), ``loan_is_ar_loan`` (related).
  - Adds ``action_generate_invoice`` and ``action_open_invoice``.

- ``account.move.line``

  - Overrides ``reconcile`` to close an Argentinian loan once all of its capital
    is reconciled.

**Vistas incluidas**

- Inherits the ``account.loan`` form: register-disbursement header button,
  disbursement/bills smart buttons, Argentinian settings in the loan settings
  column (hiding the native long/short-term, expense and journal fields), and
  the ``is_ar_loan`` toggle.
- Inherits the ``account.loan.line`` list: grace-period, capital-reconciled,
  capital-move-line and bill columns, plus the *Generate Bill* / *View Bill*
  buttons.

No new models or security rules are added; the native ``account_loans`` access
rights are reused.

Uso
===

1. **Setup** — create a dedicated bank contact (e.g. "Bank X - LOAN") and set
   its *Account Payable* to a reconcilable "Loans payable" account. For a real
   Argentinian database, also set the contact's AFIP responsibility type.
2. **Create the loan** — in Accounting, create a loan and its amortization
   schedule as usual. Keep *Argentinian Loan* enabled and fill the bank contact,
   bank journal, interest account and default VAT (the loan payable account is
   filled from the contact).
3. **Confirm** — the loan moves to *running* without generating the native
   monthly entries.
4. **Register the disbursement** — with the header button; the bank is debited
   and the capital is credited per instalment on the payable account.
5. **Generate the bill** — per instalment, with *Generate Bill*; complete the
   document type/number, VAT and perceptions against the bank's document and
   post it.
6. **Pay** — register a standard payment to the bank contact for the full
   instalment (capital + interest) and reconcile it against the capital line and
   the bill. The loan closes once all capital is reconciled.

Arquitectura
============

The module extends ``account_loans`` without modifying it. The central design
piece is a dedicated bank contact whose payable account holds both the capital
(from the disbursement entry) and the interest bills, so a single standard
payment reconciles them.

Because the Argentinian moves are linked through new fields
(``disbursement_move_id`` on the loan and ``invoice_id`` on the loan line)
rather than the native ``generating_loan_line_id``, this module overrides the
teardown (cancel / set to draft / delete), the outstanding-balance computation
and the closing logic (via ``account.move.line.reconcile``) so they account for
the Argentinian moves.

Dependencias
============

- ``account_loans``
- ``l10n_ar``
- ``account_invoice_tax``

Autor
=====

ADHOC SA

Licencia
========

AGPL-3
