from odoo import Command, _, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL


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

    def _proceed_with_locking(self, options_to_inject=None):
        """
        For Argentinian provincial tax returns and sicore, we handle the locking process differently.
        - No queremos tener lock de fechas (Solo en tax return)
        - No queremos que el asiento haga carryover de saldos (porque estamos compartiendo cuentas contables). Además
        usamos la cuenta AP del partner del reporte
        - Entonces por ahora directamente pisamos método. Otra alternativa es pisar "_generate_tax_closing_entries" y
        hacer como estabamos haciendo antes de este commit
        """
        if self.type_id.report_id != self.env.ref("l10n_ar_reports.l10n_ar_vat_book_report"):
            self._check_failing_checks_in_current_stage()

            options = {**self._get_closing_report_options(), **(options_to_inject or {})}
            # Generate PDF attachments
            self._generate_locking_attachments(options)
            # Generate simple closing entry (no carryover)
            self._generate_ar_simple_closing_entry(options)

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

    def _generate_ar_simple_closing_entry(self, options):
        """
        Generate a simple closing entry for AR provincial tax returns.
        This creates closing entries without the carryover mechanism (no "Balance tax current account" lines).
        Uses the partner's property_account_payable_id instead of tax group accounts.
        """
        self.ensure_one()

        closing_move_vals = []
        for company in self.company_ids:
            line_ids_vals = self._compute_ar_simple_closing_lines(company, options)

            if not line_ids_vals:
                continue

            closing_move_vals.append(
                {
                    "company_id": company.id,
                    "journal_id": company._get_tax_closing_journal().id,
                    "date": self.date_to,
                    "closing_return_id": self.id,
                    "ref": self.name,
                    "line_ids": line_ids_vals,
                }
            )

        if closing_move_vals:
            moves = self.env["account.move"].sudo().create(closing_move_vals)
            moves.action_post()

    def _compute_ar_simple_closing_lines(self, company, options):
        """
        Compute the closing entry lines for AR provincial tax returns.
        Returns move line commands that:
        - Reverse the balance of each tax account (like standard closing)
        - Create a single payable/receivable line using the partner's AP/AR account
        """
        self.env.flush_all()

        query = self.type_id.report_id._get_report_query(
            options,
            "strict_range",
            domain=[("company_id", "=", company.id)] + self._get_ar_tax_domain_for_return_type(),
        )

        # Get tax name with translation support
        tax_name = self.env["account.tax"]._field_to_sql("tax", "name")

        query = SQL(
            """
            SELECT "account_move_line".tax_line_id as tax_id,
                    %(tax_name)s as tax_name,
                    "account_move_line".account_id,
                    COALESCE(SUM("account_move_line".balance), 0) as amount
            FROM account_tax tax, account_tax_repartition_line repartition, %(table_references)s
            WHERE %(search_condition)s
              AND tax.id = "account_move_line".tax_line_id
              AND repartition.id = "account_move_line".tax_repartition_line_id
              AND repartition.use_in_tax_closing
            GROUP BY "account_move_line".tax_line_id, tax.name, "account_move_line".account_id
            """,
            tax_name=tax_name,
            table_references=query.from_clause,
            search_condition=query.where_clause,
        )
        self.env.cr.execute(query)
        results = self.env.cr.dictfetchall()

        move_vals_lines = []
        total = 0
        currency = company.currency_id

        for result in results:
            tax_name = result.get("tax_name")
            account_id = result.get("account_id")
            amt = result.get("amount", 0)

            if currency.is_zero(amt):
                continue

            # Line to balance the tax account (reverse the balance)
            move_vals_lines.append(
                Command.create(
                    {
                        "name": tax_name,
                        "debit": abs(amt) if amt < 0 else 0,
                        "credit": amt if amt > 0 else 0,
                        "account_id": account_id,
                    }
                )
            )
            total += amt

        # Add the final payable/receivable line using partner's account
        if not currency.is_zero(total) and move_vals_lines:
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
                account = partner.with_company(company).property_account_payable_id
                line_name = _("Tax to pay")
            else:
                # Credit in favor (positive balance means tax credit)
                account = partner.with_company(company).property_account_receivable_id
                line_name = _("Tax credit")

            if not account:
                raise UserError(
                    _(
                        "The partner '%s' has no %s account configured for company '%s'.",
                        partner.name,
                        _("payable") if total < 0 else _("receivable"),
                        company.name,
                    )
                )

            move_vals_lines.append(
                Command.create(
                    {
                        "name": line_name,
                        "debit": total if total > 0 else 0,
                        "credit": abs(total) if total < 0 else 0,
                        "account_id": account.id,
                        "partner_id": partner.id,
                    }
                )
            )

        return move_vals_lines

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
