from odoo import Command, _, fields, models
from odoo.exceptions import UserError


class AccountReturn(models.Model):
    _inherit = "account.return"

    def _get_closing_report_options(self):
        """Extends to handle sub-monthly periods like fortnightly.

        For sub-monthly periods, we use 'custom' filter instead of 'custom_return_period'
        to avoid JS errors when months_per_period is 0. We also set months_per_period to 1
        to prevent division by zero errors in the JS filters component.
        """
        options = super()._get_closing_report_options()

        # For sub-monthly periods, use 'custom' filter and fake months_per_period
        # to avoid JS calculation errors with division by 0
        if self.type_id._is_sub_monthly_period(self.company_id):
            options["date"]["filter"] = "custom"
            options["date"]["date_from"] = fields.Date.to_string(self.date_from)
            # Set months_per_period to 1 to avoid JS division by zero errors
            # The 'custom' filter won't use this value anyway
            if "return_periodicity" in options:
                options["return_periodicity"]["months_per_period"] = 1

        return options

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        domain += self._get_ar_tax_domain_for_return_type()
        return domain

    def _get_ar_tax_domain_for_return_type(self):
        """
        Returns the domain to filter tax move lines for the current return type.
        Used both by _get_vat_closing_entry_additional_domain and _generate_ar_simple_closing_entry.
        """
        if self.type_external_id == "l10n_ar_account_reports.ar_caba_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "C"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_pba_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "B"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_iva_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id", "=", False),
                ("tax_line_id.tax_group_id.l10n_ar_tribute_afip_code", "=", "06"),
                "|",
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "customer"),
                ("tax_line_id.type_tax_use", "=", "purchase"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_mendoza_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "M"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_misiones_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "N"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                ("tax_line_id.type_tax_use", "=", "sale"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_santa_fe_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "S"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_sifere_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id", "!=", False),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "purchase"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "customer"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_sircar_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "not in", ["C", "B", "T"]),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_tucuman_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "T"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.sicore_return_type":
            return [
                ("tax_line_id.l10n_ar_tax_type", "in", ["earnings", "earnings_scale"]),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
                ("tax_line_id.country_code", "=", "AR"),
            ]
        return []

    def _is_ar_simple_closing_return(self):
        """Check if this return should use simple closing (no carryover, no tax_lock_date)."""
        return self.company_id.country_id.code == "AR" and self.type_id.report_id != self.env.ref(
            "l10n_ar_reports.l10n_ar_vat_book_report"
        )

    def _proceed_with_locking(self, options_to_inject=None):
        """
        For Argentinian provincial tax returns and sicore, we handle the locking process differently.
        - No queremos tener lock de fechas (Solo en tax return)
        - No queremos que el asiento haga carryover de saldos (porque estamos compartiendo cuentas contables). Además
        usamos la cuenta AP del partner del reporte
        - Entonces por ahora directamente pisamos método. Otra alternativa es pisar "_generate_tax_closing_entries" y
        hacer como estabamos haciendo antes de este commit
        """
        if self._is_ar_simple_closing_return():
            self._check_failing_checks_in_current_stage()

            options = {**self._get_closing_report_options(), **(options_to_inject or {})}
            # Generate PDF attachments
            self._generate_locking_attachments(options)
            # Generate closing entry using standard method (our _add_tax_group_closing_items override handles the simple counterpart)
            self._generate_tax_closing_entries(options)

            # Calculate amount to pay from the partner line in closing move
            # For AR simple closing, period_amount_to_pay = total_amount_to_pay (no carryover)
            self._compute_ar_amount_to_pay()

            # Set lock date and change state (but do NOT modify tax_lock_date)
            self.date_lock = fields.Date.context_today(self)
            self.state = "reviewed"

            # Handle workflow
            if self.type_id.states_workflow == "generic_state_review":
                return self._mark_completed()

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "success",
                    "title": _("Checks Validated"),
                    "message": _("Closing entry posted."),
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        return super()._proceed_with_locking(options_to_inject=options_to_inject)

    def _compute_ar_amount_to_pay(self):
        """
        Compute the amount to pay for AR simple closing returns.
        Since we don't use carryover, period_amount_to_pay = total_amount_to_pay.
        The amount is calculated from the partner line in the closing move.
        """
        partner = self.type_id.payment_partner_id
        if not partner or not self.closing_move_ids:
            return

        # Find the line with the payment partner (the AP/AR line we created)
        partner_lines = self.closing_move_ids.line_ids.filtered(
            lambda l: l.partner_id == partner and l.account_id.account_type in ("asset_receivable", "liability_payable")
        )

        # Amount to pay is the negative of the balance (credit = positive amount to pay)
        amount = -sum(partner_lines.mapped("balance"))
        self.total_amount_to_pay = self.amount_to_pay_currency_id.round(amount)
        self.period_amount_to_pay = self.total_amount_to_pay

    def _ensure_tax_group_configuration_for_tax_closing(self):
        """
        EXTENDS account_reports
        Skip tax group account validation for AR simple closing returns,
        since we use the partner's AP/AR accounts instead of tax group accounts.
        """
        if self._is_ar_simple_closing_return():
            return
        return super()._ensure_tax_group_configuration_for_tax_closing()

    def _add_tax_group_closing_items(self, tax_group_subtotal):
        """
        EXTENDS account_reports
        For AR simple closing returns, create a simple counterpart line using the partner's AP/AR account.
        This avoids the carryover mechanism (no "Balance tax current account" lines).
        """
        if not self._is_ar_simple_closing_return():
            return super()._add_tax_group_closing_items(tax_group_subtotal)

        # Sum all tax group subtotals to get the total amount
        total = sum(tax_group_subtotal.values())
        currency = self.company_id.currency_id

        if currency.is_zero(total):
            return []

        partner = self.type_id.payment_partner_id
        if not partner:
            raise UserError(
                _(
                    "The return type '%s' has no payment partner configured. "
                    "Please set a Payment Partner on the return type.",
                    self.type_id.name,
                )
            )

        # Use partner's payable account for amounts to pay, receivable for credits
        if total < 0:
            # Amount to pay (negative balance means we owe taxes)
            account = partner.with_company(self.company_id).property_account_payable_id
            line_name = _("Tax to pay")
        else:
            # Credit in favor (positive balance means tax credit)
            account = partner.with_company(self.company_id).property_account_receivable_id
            line_name = _("Tax credit")

        if not account:
            raise UserError(
                _(
                    "The partner '%s' has no %s account configured for company '%s'.",
                    partner.name,
                    _("payable") if total < 0 else _("receivable"),
                    self.company_id.name,
                )
            )

        return [
            Command.create(
                {
                    "name": line_name,
                    "debit": total if total > 0 else 0,
                    "credit": abs(total) if total < 0 else 0,
                    "account_id": account.id,
                    "partner_id": partner.id,
                }
            )
        ]

    def _run_checks(self, check_codes_to_ignore):
        if "l10n_ar_account_reports." in self.type_external_id:
            # por ahora ignoramos todos los checks nativos para simplificar
            check_codes_to_ignore.update(
                [
                    "check_bills_attachment",
                    "check_draft_entries",
                    "check_match_all_bank_entries",
                    "check_tax_countries",
                    "check_company_data",
                ]
            )
        return super()._run_checks(check_codes_to_ignore)

    def _get_pay_wizard(self):
        # EXTENDS account_reports
        if self.company_id.country_id.code == "AR" and self.is_tax_return and self.type_id.payment_partner_id:
            line_to_pay = self.closing_move_ids.line_ids.filtered(
                lambda l: l.partner_id == self.type_id.payment_partner_id
                and l.account_id.account_type in ("asset_receivable", "liability_payable")
            )
            if line_to_pay:
                return line_to_pay.action_register_payment()
        return super()._get_pay_wizard()

    def _update_payment_state(self):
        """Método manual para actualizar el estado basado en conciliación"""
        for record in self:
            if record.closing_move_ids:
                lines_to_pay = record.closing_move_ids.line_ids.filtered(
                    lambda l: l.partner_id == record.type_id.payment_partner_id
                    and l.account_id.account_type in ("asset_receivable", "liability_payable")
                )
                if lines_to_pay:
                    is_paid = all(lines_to_pay.mapped("reconciled"))
                    workflow_field = record.type_id.states_workflow
                    if is_paid and record.state != "paid":
                        record.state = "paid"
                    elif not is_paid and record.state == "paid":
                        # Si se desconcilia, volvemos al estado anterior según el workflow
                        if workflow_field == "generic_state_tax_report":
                            record.state = "submitted"
                        else:
                            record.state = "reviewed"
