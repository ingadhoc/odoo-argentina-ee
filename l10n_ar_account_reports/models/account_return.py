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
        l10n_ar_domain = self.type_id._get_l10n_ar_activity_domain()
        if l10n_ar_domain:
            domain += l10n_ar_domain
        return domain

    def _is_ar_simple_closing_return(self):
        """Check if this return should use simple closing (no carryover, no tax_lock_date)."""
        return self.company_id.country_id.code == "AR" and self.type_id != self.env.ref(
            "l10n_ar_reports.ar_tax_return_type"
        )

    def _ensure_tax_group_configuration_for_tax_closing(self):
        """
        Skip tax group account validation for AR simple closing returns,
        since we use the partner's AP/AR accounts instead of tax group accounts.
        NOTA: esto de acá no suma tanto porque si se quiere liquidar el informde "vat" u otro igual se van a chequear
        todas las cuentas
        """
        if self._is_ar_simple_closing_return():
            return
        return super()._ensure_tax_group_configuration_for_tax_closing()

    def _get_tax_closing_payable_and_receivable_accounts(self):
        """Get the payable and receivable accounts for tax closing.

        For AR simple closing returns:
        - Uses debt_account_id if configured in return type
        - Falls back to payment_partner_id accounts if no debt_account_id
        """
        if self._is_ar_simple_closing_return():
            debt_account = self.type_id.debt_account_id
            partner = self.type_id.payment_partner_id

            if debt_account:
                # When debt_account_id is set, use it for both payable and receivable
                # (the system will use the appropriate side based on balance)
                return debt_account, debt_account
            elif partner:
                # Fall back to partner accounts
                return (
                    partner.with_company(self.company_id).property_account_payable_id,
                    partner.with_company(self.company_id).property_account_receivable_id,
                )
            else:
                # No configuration found, will fail in _add_tax_group_closing_items
                return False, False

        return super()._get_tax_closing_payable_and_receivable_accounts()

    def _on_post_submission_event(self):
        """No queremos que luego de submit dispare directamente pago, prefiero que se haga click en en boton,
        mas adelante se puede implementar un wizard de submit o similar como hacen otros heredando método action_submit
        """
        if self._is_ar_simple_closing_return():
            if self.type_id.states_workflow == "generic_state_review_submit":
                return self._mark_completed()
            return
        return super()._on_post_submission_event()

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

        # Priority 1: Use debt_account_id if configured
        if self.type_id.debt_account_id:
            account = self.type_id.debt_account_id
        # Priority 2: Use partner's payable/receivable account
        elif partner:
            # Use partner's payable account for amounts to pay, receivable for credits
            if total < 0:
                # Amount to pay (negative balance means we owe taxes)
                account = partner.with_company(self.company_id).property_account_payable_id
            else:
                # Credit in favor (positive balance means tax credit)
                account = partner.with_company(self.company_id).property_account_receivable_id

            if not account:
                raise UserError(
                    _(
                        "The partner '%s' has no %s account configured for company '%s'.",
                        partner.name,
                        _("payable") if total < 0 else _("receivable"),
                        self.company_id.name,
                    )
                )
        else:
            raise UserError(
                _(
                    "The return type '%s' has no debt account or payment partner configured. "
                    "Please set a Debt Account or Payment Partner on the return type.",
                    self.type_id.name,
                )
            )

        # Determine line name based on amount sign
        if total < 0:
            line_name = _("Tax to pay")
        else:
            line_name = _("Tax credit")

        return [
            Command.create(
                {
                    "name": line_name,
                    "debit": total if total > 0 else 0,
                    "credit": abs(total) if total < 0 else 0,
                    "account_id": account.id,
                    "partner_id": partner.id if partner else False,
                }
            )
        ]

    def _proceed_with_locking(self, options_to_inject=None):
        """
        For Argentinian provincial tax returns (Ingresos Brutos), we handle the locking process differently.
        We don't want to set the tax_lock_date when validating the "asiento de liquidación".
        We temporarily store the current tax_lock_date, call super(), then restore it to prevent changes.
        """
        tax_lock_dates = {
            company: company.tax_lock_date for company in self.company_ids.filtered(lambda c: c.country_id.code == "AR")
        }
        # mandamos contexto para que no se postee si no queremos
        res = super(AccountReturn, self.with_context(post_from_tax_return=True))._proceed_with_locking(
            options_to_inject=options_to_inject
        )

        # por ahora no queremos ningun informe argentino que haga lock porque, IVA, que es el principal lo estamos
        # dejando editable para que el usuario termine de acomodarlo, luego deberá hacer lock manualmente
        if self._is_ar_simple_closing_return():
            # Restore tax_lock_date to prevent it from being modified by provincial returns
            for company, original_date in tax_lock_dates.items():
                if company.tax_lock_date != original_date:
                    company.sudo().tax_lock_date = original_date

        # si no posteamos devolvemos acción
        if self.closing_move_ids.filtered(lambda m: m.state == "draft"):
            # para el libro de IVA asignamos también el partner si está definido
            if self.type_id == self.env.ref("l10n_ar_reports.ar_tax_return_type") and self.type_id.payment_partner_id:
                self.closing_move_ids.line_ids.filtered(
                    lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
                ).partner_id = self.type_id.payment_partner_id.id
            return self.closing_move_ids._get_records_action()
        return res

    def _get_common_check_domain(self):
        """Build common domain filters for all checks."""
        return [
            ("company_id.account_fiscal_country_id.code", "=", "AR"),
            ("company_id", "in", self.company_ids.ids),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
        ]

    def _create_check_dict(self, name, message, code, records_count, records_model, domain):
        """Create a standardized check dictionary."""
        action = (
            {
                "type": "ir.actions.act_window",
                "name": name,
                "view_mode": "list",
                "res_model": records_model,
                "domain": domain,
                "views": [[False, "list"], [False, "form"]],
            }
            if records_count
            else False
        )
        return {
            "name": name,
            "message": message,
            "code": code,
            "records_count": records_count,
            "records_model": self.env["ir.model"]._get(records_model).id,
            "result": "anomaly" if records_count else "reviewed",
            "action": action,
        }

    def _check_draft_perceptions(self, state_code, state_name):
        """Check for draft perceptions for a given state."""
        domain = self._get_common_check_domain() + [
            ("tax_ids.l10n_ar_state_id.code", "=", state_code),
            ("tax_ids.type_tax_use", "=", "sale"),
            ("move_id.state", "=", "draft"),
        ]
        count = self.env["account.move.line"].search_count(domain)
        return self._create_check_dict(
            name=_("Moves with Draft %s Perceptions", state_name),
            message=_("There are draft %s perceptions in the selected period.", state_name),
            code=f"{state_code.lower()}_iibb_draft_perceptions",
            records_count=count,
            records_model="account.move.line",
            domain=domain,
        )

    def _check_draft_withholdings(self, state_code, state_name, tax_filter=None):
        """Check for draft withholdings for a given state or tax type.

        Args:
            state_code: State code to filter (e.g., 'B', 'C', 'M')
            state_name: Human readable state name
            tax_filter: Additional tax filter dict (e.g., {'l10n_ar_tax_type': ['earnings']})
        """
        domain = self._get_common_check_domain() + [("state", "=", "draft")]

        if tax_filter:
            # For special cases like SICORE (earnings withholdings)
            for key, value in tax_filter.items():
                if isinstance(value, list):
                    domain.append((f"l10n_ar_withholding_line_ids.tax_id.{key}", "in", value))
                else:
                    domain.append((f"l10n_ar_withholding_line_ids.tax_id.{key}", "=", value))
        else:
            # Standard state-based withholding checks
            domain.append(("l10n_ar_withholding_line_ids.tax_id.l10n_ar_state_id.code", "=", state_code))

        domain.append(("l10n_ar_withholding_line_ids.tax_id.l10n_ar_withholding_payment_type", "=", "supplier"))

        count = self.env["account.payment"].search_count(domain)
        return self._create_check_dict(
            name=_("Payments with Draft %s Withholdings", state_name),
            message=_("There are draft %s withholdings in the selected period.", state_name),
            code=f"{state_code.lower()}_draft_withholdings" if not tax_filter else "sicore_draft_withholdings",
            records_count=count,
            records_model="account.payment",
            domain=domain,
        )

    def _check_draft_sifere_withholdings(self):
        """Check for draft SIFERE withholdings (customer withholdings)."""
        domain = self._get_common_check_domain() + [
            ("l10n_ar_withholding_line_ids.tax_id.l10n_ar_state_id", "!=", False),
            ("l10n_ar_withholding_line_ids.tax_id.l10n_ar_withholding_payment_type", "=", "customer"),
            ("state", "=", "draft"),
        ]
        count = self.env["account.payment"].search_count(domain)
        return self._create_check_dict(
            name=_("Payments with Draft SIFERE Withholdings"),
            message=_("There are draft SIFERE withholdings in the selected period."),
            code="sifere_draft_withholdings",
            records_count=count,
            records_model="account.payment",
            domain=domain,
        )

    def _check_draft_sifere_perceptions(self):
        """Check for draft SIFERE perceptions (purchase perceptions)."""
        domain = self._get_common_check_domain() + [
            ("tax_ids.l10n_ar_state_id", "!=", False),
            ("tax_ids.type_tax_use", "=", "purchase"),
            ("move_id.state", "=", "draft"),
        ]
        count = self.env["account.move.line"].search_count(domain)
        return self._create_check_dict(
            name=_("Moves with Draft SIFERE Perceptions"),
            message=_("There are draft SIFERE perceptions in the selected period."),
            code="sifere_draft_perceptions",
            records_count=count,
            records_model="account.move.line",
            domain=domain,
        )

    def _check_draft_sircar_perceptions(self):
        """Check for draft SIRCAR perceptions (excluding CABA, PBA, Tucumán)."""
        domain = self._get_common_check_domain() + [
            ("tax_ids.l10n_ar_state_id.code", "not in", ["C", "B", "T"]),
            ("tax_ids.l10n_ar_state_id.country_id.code", "=", "AR"),
            ("tax_ids.type_tax_use", "=", "sale"),
            ("move_id.state", "=", "draft"),
        ]
        count = self.env["account.move.line"].search_count(domain)
        return self._create_check_dict(
            name=_("Moves with Draft SIRCAR Perceptions"),
            message=_("There are draft SIRCAR perceptions in the selected period."),
            code="sircar_draft_perceptions",
            records_count=count,
            records_model="account.move.line",
            domain=domain,
        )

    def _check_draft_sircar_withholdings(self):
        """Check for draft SIRCAR withholdings (excluding CABA, PBA, Tucumán)."""
        domain = self._get_common_check_domain() + [
            ("l10n_ar_withholding_line_ids.tax_id.l10n_ar_state_id.code", "not in", ["C", "B", "T"]),
            ("l10n_ar_withholding_line_ids.tax_id.l10n_ar_state_id.country_id.code", "=", "AR"),
            ("l10n_ar_withholding_line_ids.tax_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ("state", "=", "draft"),
        ]
        count = self.env["account.payment"].search_count(domain)
        return self._create_check_dict(
            name=_("Payments with Draft SIRCAR Withholdings"),
            message=_("There are draft SIRCAR withholdings in the selected period."),
            code="sircar_draft_withholdings",
            records_count=count,
            records_model="account.payment",
            domain=domain,
        )

    def _run_checks(self, check_codes_to_ignore):
        """
        EXTENDS account_reports
        Run specific checks for Argentinian tax returns based on return type.
        """
        if self.company_id.country_id.code != "AR" or not self.is_tax_return:
            return super()._run_checks(check_codes_to_ignore)

        # Mapping of return types to their check methods
        checks_mapping = {
            "l10n_ar_account_reports.sicore_return_type": [
                lambda: self._check_draft_withholdings(
                    state_code="SICORE",
                    state_name="Earnings",
                    tax_filter={"l10n_ar_tax_type": ["earnings", "earnings_scale"]},
                )
            ],
            "l10n_ar_account_reports.ar_caba_iibb_return_type": [
                lambda: self._check_draft_perceptions("C", "CABA"),
                lambda: self._check_draft_withholdings("C", "CABA"),
            ],
            "l10n_ar_account_reports.ar_pba_iibb_return_type": [
                lambda: self._check_draft_perceptions("B", "PBA"),
                lambda: self._check_draft_withholdings("B", "PBA"),
            ],
            "l10n_ar_account_reports.ar_mendoza_iibb_return_type": [
                lambda: self._check_draft_withholdings("M", "Mendoza"),
            ],
            "l10n_ar_account_reports.ar_misiones_iibb_return_type": [
                lambda: self._check_draft_perceptions("N", "Misiones"),
                lambda: self._check_draft_withholdings("N", "Misiones"),
            ],
            "l10n_ar_account_reports.ar_santa_fe_iibb_return_type": [
                lambda: self._check_draft_perceptions("S", "Santa Fe"),
                lambda: self._check_draft_withholdings("S", "Santa Fe"),
            ],
            "l10n_ar_account_reports.ar_tucuman_iibb_return_type": [
                lambda: self._check_draft_perceptions("T", "Tucumán"),
                lambda: self._check_draft_withholdings("T", "Tucumán"),
            ],
            "l10n_ar_account_reports.ar_sifere_iibb_return_type": [
                self._check_draft_sifere_withholdings,
                self._check_draft_sifere_perceptions,
            ],
            "l10n_ar_account_reports.ar_sircar_iibb_return_type": [
                self._check_draft_sircar_perceptions,
                self._check_draft_sircar_withholdings,
            ],
        }

        # Get check methods for this return type
        check_methods = checks_mapping.get(self.type_external_id, [])

        if check_methods:
            # Execute all checks for this return type
            checks = [check_method() for check_method in check_methods]
            return checks

        # For other AR return types, ignore some standard checks
        check_codes_to_ignore.update(
            [
                "check_bills_attachment",
                # "check_draft_entries",  # Keep this check as it's useful
                "check_match_all_bank_entries",
                "check_tax_countries",  # Odoo checks FP country equals partner country, not useful
                "check_company_data",
            ]
        )
        return super()._run_checks(check_codes_to_ignore)

    def _get_pay_wizard(self):
        # EXTENDS account_reports
        if self.company_id.country_id.code == "AR" and self.is_tax_return:
            # Filter lines by debt_account_id or partner's account
            if self.type_id.debt_account_id:
                line_to_pay = self.closing_move_ids.line_ids.filtered(
                    lambda l: l.account_id == self.type_id.debt_account_id
                )
            elif self.type_id.payment_partner_id:
                line_to_pay = self.closing_move_ids.line_ids.filtered(
                    lambda l: l.partner_id == self.type_id.payment_partner_id
                    and l.account_id.account_type in ("asset_receivable", "liability_payable")
                )
            else:
                line_to_pay = self.env["account.move.line"]

            if line_to_pay:
                return line_to_pay.action_register_payment()
        return super()._get_pay_wizard()

    def _update_payment_state(self):
        """Método manual para actualizar el estado basado en conciliación"""
        for record in self:
            if record.closing_move_ids:
                # Filter lines by debt_account_id or partner's account
                if record.type_id.debt_account_id:
                    lines_to_pay = record.closing_move_ids.line_ids.filtered(
                        lambda l: l.account_id == record.type_id.debt_account_id
                    )
                elif record.type_id.payment_partner_id:
                    lines_to_pay = record.closing_move_ids.line_ids.filtered(
                        lambda l: l.partner_id == record.type_id.payment_partner_id
                        and l.account_id.account_type in ("asset_receivable", "liability_payable")
                    )
                else:
                    lines_to_pay = record.env["account.move.line"]

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
