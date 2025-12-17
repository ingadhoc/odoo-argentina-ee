from odoo import models


class AccountReturn(models.Model):
    _inherit = "account.return"

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

    ####################################################################################################
    ####  Tax Closing
    ####################################################################################################
    def _generate_tax_closing_entries(self, options):
        """
        Generates and compute a closing move for every companies of the return.
        :param options: report options
        :return: The closing moves.
        """
        self.ensure_one()
        # self._ensure_tax_group_configuration_for_tax_closing()

        closing_move_vals = []
        for company in self.company_ids:
            line_ids_vals, tax_group_subtotal = self.sudo()._compute_tax_closing_entry(company, options)
            line_ids_vals += self.sudo()._add_tax_group_closing_items(tax_group_subtotal)
            closing_move_vals.append(
                {
                    "company_id": company.id,  # Important to specify together with the journal, for branches
                    "journal_id": company._get_tax_closing_journal().id,
                    "date": self.date_to,
                    "closing_return_id": self.id,
                    "ref": self.name,
                    "line_ids": line_ids_vals,
                }
            )

        moves = self.env["account.move"].sudo().create(closing_move_vals)
        moves.action_post()

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
