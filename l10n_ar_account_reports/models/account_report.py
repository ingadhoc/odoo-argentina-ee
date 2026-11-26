from odoo import api, models


class AccountReport(models.Model):
    _inherit = "account.report"

    def _generate_common_warnings(self, options, warnings):
        """Replace the native Tax ID warning on tax unit reports of Argentinian companies.

        The native warning (``account_reports.tax_report_warning_tax_id_selected_companies``)
        only looks at the branches below the active company, so it never fires from a branch,
        and it does not say which companies were left out. Ours compares the selected companies
        with the companies of the report, so it fires from any active company, and it names the
        excluded companies (with their Tax ID, if any) and the Tax ID of the numbers. With forced
        companies (e.g. an audit report) the selection is left out on purpose, so there is no
        warning. Other countries keep the native warning.
        """
        super()._generate_common_warnings(options, warnings)

        if self.filter_multi_company != "tax_units" or self.env.company.account_fiscal_country_id.code != "AR":
            return

        warnings.pop("account_reports.tax_report_warning_tax_id_selected_companies", None)
        excluded = self.env.companies - self.env["res.company"].browse(self.get_report_company_ids(options))
        # Forced companies (e.g. an audit report) leave the selection out on purpose.
        if excluded and not options.get("forced_companies"):
            entity = self.env.company.sudo().legal_entity_root_id
            warnings["l10n_ar_account_reports.warning_other_legal_entity_companies"] = {
                "alert_type": "warning",
                "entity": entity.display_name,
                "vat": entity.vat or "-",
                "excluded": ", ".join(
                    f"{company.display_name} ({company.vat})" if company.vat else company.display_name
                    for company in excluded.sudo()
                ),
            }

    @api.model
    def _compute_period_range(self, date, months_per_period, start_day, start_month):
        """Un tipo de declaración quincenal no tiene meses por período, y el cálculo nativo divide por eso.

        ``_compute_period_range`` de account_reports hace ``month_offset // months_per_period`` y
        revienta con ZeroDivisionError; llegan ahí ``_get_period_dates`` y
        ``_get_shifted_dates_period``. Con 0 meses por período el período es la quincena, que es
        lo que ``account.return.type._get_sub_monthly_period_boundaries`` ya resuelve.
        """
        if not months_per_period:
            return self.env["account.return.type"]._l10n_ar_fortnight_boundaries(date)
        return super()._compute_period_range(date, months_per_period, start_day, start_month)
