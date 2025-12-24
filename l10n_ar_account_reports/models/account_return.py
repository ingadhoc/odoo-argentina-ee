from odoo import fields, models


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
        elif self.type_external_id == "l10n_ar_account_reports.ar_iva_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id", "=", False),
                "|",
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "customer"),
                ("tax_line_id.type_tax_use", "=", "purchase"),
                ("tax_line_id.tax_group_id.l10n_ar_tribute_afip_code", "=", "06"),
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
                ("tax_line_id.type_tax_use", "=", "sale"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_santa_fe_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id.code", "=", "S"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                ("tax_line_id.type_tax_use", "=", "sale"),
                "|",
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_sifere_iibb_return_type":
            domain += [
                ("tax_line_id.l10n_ar_state_id", "!=", False),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                ("tax_line_id.type_tax_use", "=", "purchase"),
                "|",
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
        elif self.type_external_id == "l10n_ar_account_reports.sicore_return_type":
            domain += [
                ("tax_line_id.l10n_ar_tax_type", "in", ["earnings", "earnings_scale"]),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
                ("tax_line_id.country_code", "=", "AR"),
            ]
        return domain

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

    def _proceed_with_locking(self, options_to_inject=None):
        """
        EXTENDS account_reports
        For Argentinian provincial tax returns (Ingresos Brutos), we handle the locking process differently.
        We don't want to set the tax_lock_date when validating the "asiento de liquidación".
        We temporarily store the current tax_lock_date, call super(), then restore it to prevent changes.
        """
        tax_lock_dates = {
            company: company.tax_lock_date for company in self.company_ids.filtered(lambda c: c.country_id.code == "AR")
        }
        res = super()._proceed_with_locking(options_to_inject=options_to_inject)
        if (
            self.type_id
            and self.type_id.report_id
            and self.is_tax_return
            and self.type_id.report_id.country_id.code == "AR"
            and self.company_id.country_id.code == "AR"
        ):
            # Restore tax_lock_date to prevent it from being modified by provincial returns
            for company, original_date in tax_lock_dates.items():
                if company.tax_lock_date != original_date:
                    company.sudo().tax_lock_date = original_date
        return res
