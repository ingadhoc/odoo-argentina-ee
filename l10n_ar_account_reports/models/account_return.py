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
                ("tax_line_id.type_tax_use", "=", "sale"),
            ]
        elif self.type_external_id == "l10n_ar_account_reports.ar_pba_iibb_return_type":
            # mod_tags = self.env.ref('l10n_es.mod_303').line_ids.expression_ids._get_matching_tags()
            # domain.append(('tax_tag_ids', 'in', mod_tags.ids))
            domain += [
                ("tax_line_id.l10n_ar_state_id.code", "=", "B"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                ("tax_line_id.type_tax_use", "=", "sale"),
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
