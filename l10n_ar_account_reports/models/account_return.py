from odoo import Command, _, api, fields, models
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

    def _ensure_tax_group_configuration_for_tax_closing(self):
        """
        Skip tax group account validation for AR simple closing returns,
        since we use the partner's AP/AR accounts instead of tax group accounts.
        NOTA: esto de acá no suma tanto porque si se quiere liquidar el informde "vat" u otro igual se van a chequear
        todas las cuentas
        """
        if self.type_id.l10n_ar_is_simple_closing_return:
            return
        return super()._ensure_tax_group_configuration_for_tax_closing()

    # ver en _compute_show_amount_to_pay
    # def _get_tax_closing_payable_and_receivable_accounts(self):
    #     """Eso es necesario para que los importes total_amount_to_pay y period_amount_to_pay se calcule bien"""
    #     if self._is_ar_simple_closing_return():
    #         partner = self.type_id.payment_partner_id
    #         return partner.with_company(self.company_id).property_account_payable_id, partner.with_company(
    #             self.company_id
    #         ).property_account_receivable_id
    #     return super()._get_tax_closing_payable_and_receivable_accounts()

    @api.depends(
        "type_id.l10n_ar_is_simple_closing_return",
    )
    def _compute_show_amount_to_pay(self):
        """
        Para liquidaciones simples de Argentina, los importes calculados por Odoo al bloquear el informe
        pueden no ser representativos si el asiento fue modificado manualmente o si no se utiliza
        la configuración estándar de grupos de impuestos. Ocultamos el bloque si los importes son cero
        para evitar mostrar información irrelevante o confusa.
        TODO mas adelante podriamos:
        a) borrar el partche en "_proceed_with_locking"
        b) dejar que los montos se muestren para los asientos que se publicana automáticamente y/o mejorar para que
        cambiar asiento manualmente actualice los montos
        c) agregar en condición de abajo "and not record.total_amount_to_pay and not record.period_amount_to_pay"

        Por ahora vamos por lo simple
        """
        super()._compute_show_amount_to_pay()
        for record in self:
            if record.type_id.l10n_ar_is_simple_closing_return:
                record.show_amount_to_pay = False

    def _on_post_submission_event(self):
        """No queremos que luego de submit dispare directamente pago, prefiero que se haga click en en boton,
        mas adelante se puede implementar un wizard de submit o similar como hacen otros heredando método action_submit
        """
        if self.type_id.l10n_ar_is_simple_closing_return:
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
        if not self.type_id.l10n_ar_is_simple_closing_return:
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

        # Check if a specific account is configured on the return type
        configured_account = self.type_id.l10n_ar_account_id

        line_name = _("Tax to pay") if total < 0 else _("Tax credit")
        if configured_account:
            # Use the configured account from the return type
            account = configured_account
        else:
            # Fallback: Use partner's payable account for amounts to pay, receivable for credits
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
        if self.type_id.l10n_ar_is_simple_closing_return:
            # ver notas en _compute_show_amount_to_pay
            self.write({"total_amount_to_pay": False, "period_amount_to_pay": False})

            # Restore tax_lock_date to prevent it from being modified by provincial returns
            for company, original_date in tax_lock_dates.items():
                if company.tax_lock_date != original_date:
                    company.sudo().tax_lock_date = original_date

        # si no posteamos devolvemos acción
        if self.closing_move_ids.filtered(lambda m: m.state == "draft"):
            return self.closing_move_ids._get_records_action()
        return res

    def _run_checks(self, check_codes_to_ignore):
        # if "l10n_ar_account_reports." in self.type_external_id:
        # smplificamos check de todos los reportes argentinos
        if self.company_id.country_id.code == "AR" and self.is_tax_return:
            # por ahora ignoramos todos los checks nativos para simplificar
            check_codes_to_ignore.update(
                [
                    "check_bills_attachment",
                    # "check_draft_entries",  # este nos parece útil
                    "check_match_all_bank_entries",
                    "check_tax_countries",  # odoo chequea que el country de la FP sea igual al del partner, no le vemos utlidad
                    "check_company_data",
                ]
            )
        return super()._run_checks(check_codes_to_ignore)

    def _get_pay_wizard(self):
        # EXTENDS account_reports
        if self.company_id.country_id.code == "AR" and self.is_tax_return and self.type_id.payment_partner_id:
            lines_to_pay = self.closing_move_ids.line_ids.filtered(
                lambda l: l.partner_id == self.type_id.payment_partner_id
                and l.account_id.account_type in ("asset_receivable", "liability_payable")
            )
            # si el saldo es a favor (balance >= 0), actualizamos estado y no abrimos wizard
            if lines_to_pay and sum(lines_to_pay.mapped("balance")) >= 0:
                self._update_payment_state()
                return
            if lines_to_pay:
                return lines_to_pay.action_register_payment()
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
                    # Si el saldo es "a favor" (balance >= 0) o está conciliado, lo pasamos a pagado
                    is_paid = sum(lines_to_pay.mapped("balance")) >= 0 or all(lines_to_pay.mapped("reconciled"))
                    workflow_field = record.type_id.states_workflow
                    if is_paid and record.state != "paid":
                        record.state = "paid"
                    elif not is_paid and record.state == "paid":
                        # Si se desconcilia, volvemos al estado anterior según el workflow
                        if workflow_field == "generic_state_tax_report":
                            record.state = "submitted"
                        else:
                            record.state = "reviewed"
