from odoo import fields, models


class AccountReturn(models.Model):
    _inherit = "account.return"

    def _run_checks(self, check_codes_to_ignore):
        checks = super()._run_checks(check_codes_to_ignore)
        if self.type_external_id == "l10n_ar_account_reports.ar_pba_iibb_return_type":
            checks += self._check_suite_ar_pba_iibb_report()

        return checks

    def _check_suite_ar_pba_iibb_report(self):
        """Este check verifica que para arba las percepciones sean cargadas en un diario que usa documentos"""
        checks = []
        report_options = self._get_closing_report_options()
        domain = self.type_id.report_id._get_options_domain(report_options, "strict_range")
        domain += [
            ("move_id.state", "=", "posted"),
            ("company_id", "in", self.company_ids.ids),
            ("date", "<=", fields.Date.to_string(self.date_to)),
            ("date", ">=", fields.Date.to_string(self.date_from)),
            ("journal_id.l10n_latam_use_documents", "=", False),
        ]
        # TODO mejorar porque está re hardcodeado
        import ast

        domain += ast.literal_eval(self.type_id.report_id.line_ids.expression_ids[1].formula)

        draft_entries_count = self.env["account.move.line"].sudo().search_count(domain)
        blaa = self.env["account.move.line"].sudo().search(domain)

        review_action = {
            "type": "ir.actions.act_window",
            "name": "wdewd",  # If it is _lt, we need to stringify it because it cannot be json dumped
            "view_mode": "list",
            "res_model": "account.move",
            "domain": [["id", "in", blaa.mapped("move_id").ids]],
            "views": [[self.env.ref("account_reports.view_draft_entries_tree").id, "list"], [False, "form"]],
        }

        checks.append(
            {
                "name": "Percepciones sin punto de venta-número",
                "code": "xcd",
                "message": "Las percepciones deben ser cargadas en un diario que usa documentos",
                "records_count": draft_entries_count,
                "records_model": self.env["ir.model"]._get("account.move").id,
                "action": review_action if draft_entries_count else None,
                "result": "anomaly" if draft_entries_count else "reviewed",
            }
        )
        return checks

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
        self._ensure_tax_group_configuration_for_tax_closing()

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
