from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = "account.return.type"

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

        if country_code == "AR":
            ar_sales_return_type = self.env.ref("l10n_ar_account_reports.ar_pba_iibb_return_type")
            offset = ar_sales_return_type._get_periodicity_months_delay(main_company)
            date_in_previous_period = fields.Date.context_today(self) - relativedelta(months=offset)
            date_from, date_to = ar_sales_return_type._get_period_boundaries(main_company, date_in_previous_period)
            tax_ids = self.env["account.tax"].filtered(lambda x: x.l10n_ar_state_id.country_id.code == "AR")

            domain = [
                ("tax_ids", "in", tax_ids),
                ("balance", "!=", 0),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
                ("parent_state", "=", "posted"),
            ]
            if self.env["account.move.line"].search_count(domain, limit=1):
                ar_sales_return_type._try_create_return_for_period(date_from, main_company, tax_unit)

        return rslt
