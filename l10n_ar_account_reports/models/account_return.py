from collections import defaultdict

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
        if self.type_external_id == "l10n_ar_account_reports.ar_caba_iibb_return_type":
            # mod_tags = self.env.ref('l10n_es.mod_303').line_ids.expression_ids._get_matching_tags()
            # domain.append(('tax_tag_ids', 'in', mod_tags.ids))
            domain += [
                ("tax_line_id.l10n_ar_state_id.code", "=", "C"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_pba_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id.code", "=", "B"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_mendoza_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id.code", "=", "M"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_misiones_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id.code", "=", "N"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_santa_fe_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id.code", "=", "S"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_sifere_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id", "!=", False),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "purchase"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "customer"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_sircar_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id.code", "not in", ["C", "B", "T"]),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_tucuman_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id.code", "=", "T"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_reports.ar_tax_return_type":
            #     domain += [
            #         ("tax_line_id.l10n_ar_state_id", "=", False),
            #         ("tax_line_id.country_code", "=", "AR"),
            #         ("tax_line_id.tax_group_id.l10n_ar_tribute_afip_code", "in", ["01", "06", "07"]),
            #     ]
            domain += [
                "|",
                # GRUPO A: Impuestos con código de IVA AFIP (Ventas o Compras)
                "&",
                ("tax_line_id.tax_group_id.l10n_ar_vat_afip_code", "!=", False),
                ("tax_line_id.type_tax_use", "in", ["sale", "purchase"]),
                # GRUPO B: Retenciones / Percepciones sufridas
                "&",
                "&",
                ("tax_line_id.l10n_ar_state_id", "=", False),
                ("tax_line_id.tax_group_id.l10n_ar_tribute_afip_code", "=", "06"),
                "|",
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "customer"),
                ("tax_line_id.type_tax_use", "=", "purchase"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.sicore_return_type":
            domain += [
                ("tax_line_id.l10n_ar_tax_type", "in", ["earnings", "earnings_scale"]),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
                ("tax_line_id.country_code", "=", "AR"),
            ]
        return domain

    def _is_ar_simple_closing_return(self):
        """Check if this return should use simple closing (no carryover, no tax_lock_date)."""
        if self.company_id.country_id.code != "AR":
            return False
        # For Argentina, we prefer simple closing (no automatic odoo carryover)
        # for almost all liquidation reports (IVA, IIBB, etc) to handle technical
        # and unrestricted balances manually or via simple counter-part lines.
        return True

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
        """Eso es necesario para que los importes total_amount_to_pay y period_amount_to_pay se calcule bien"""
        if self._is_ar_simple_closing_return():
            partner = self.type_id.payment_partner_id
            return partner.with_company(self.company_id).property_account_payable_id, partner.with_company(
                self.company_id
            ).property_account_receivable_id
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
        For AR simple closing returns, create counterpart lines based on Tax Group configuration.
        This allows separating technical balance from unrestricted balance if different accounts are set.
        """
        if not self._is_ar_simple_closing_return():
            return super()._add_tax_group_closing_items(tax_group_subtotal)

        partner = self.type_id.payment_partner_id
        if not partner:
            raise UserError(
                _(
                    "The return type '%s' has no payment partner configured. "
                    "Please set a Payment Partner on the return type.",
                    self.type_id.name,
                )
            )

        # Dictionary to group amounts by account_id
        totals_by_account = defaultdict(float)
        currency = self.company_id.currency_id

        # tax_group_subtotal keys are (advance_account_id, receivable_account_id, payable_account_id)
        # as returned by _compute_tax_closing_entry
        for (adv_id, rec_id, pay_id), amount in tax_group_subtotal.items():
            # Identify the account to use for this tax group
            # We prioritize:
            # 1. advance_tax_payment_account_id (if credit and it exists)
            # 2. tax_receivable_account_id / tax_payable_account_id
            # 3. fallback to partner properties
            account_id = False
            if amount > 0:  # Credit in favor (receivable)
                # This is the key change: if we have an advance account (adv_id is not None),
                # we use it. This allows separating Unrestricted Balance from Technical Balance.
                # NOTA: igualmente por ahora no estamos seteando adv_id en el chart y seguimos usando la rec_id
                account_id = adv_id or rec_id
                if not account_id:
                    account_id = partner.with_company(self.company_id).property_account_receivable_id.id
            else:  # Debt (payable)
                account_id = pay_id
                if not account_id:
                    account_id = partner.with_company(self.company_id).property_account_payable_id.id

            if account_id:
                totals_by_account[account_id] += amount

        res = []
        for account_id, total in totals_by_account.items():
            if currency.is_zero(total):
                continue

            account = self.env["account.account"].browse(account_id)
            # We keep the generic name if it's the partner property, otherwise use account name
            if account_id == partner.with_company(self.company_id).property_account_payable_id.id:
                line_name = _("Tax to pay")
            elif account_id == partner.with_company(self.company_id).property_account_receivable_id.id:
                line_name = _("Tax credit")
            else:
                line_name = account.name

            res.append(
                Command.create(
                    {
                        "name": line_name,
                        "debit": total if total > 0 else 0,
                        "credit": abs(total) if total < 0 else 0,
                        "account_id": account_id,
                        "partner_id": partner.id,
                    }
                )
            )
        return res

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
