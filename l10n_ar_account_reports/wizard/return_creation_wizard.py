##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class AccountReturnCreationWizard(models.TransientModel):
    _inherit = "account.return.creation.wizard"

    @api.onchange("return_type_id")
    def _onchange_return_type_id(self):
        """Extended to handle sub-monthly periods like fortnightly."""
        today = fields.Date.context_today(self)
        if self.return_type_id:
            # Check if this is a sub-monthly period (e.g., fortnightly)
            if self.return_type_id._is_sub_monthly_period(self.company_id):
                period_days = self.return_type_id._get_periodicity_days_delay(self.company_id)
                shifted_date = today - relativedelta(days=period_days)
            else:
                period_months = self.return_type_id._get_periodicity_months_delay(self.company_id)
                shifted_date = today - relativedelta(months=period_months)
            self.date_from, self.date_to = self.return_type_id._get_period_boundaries(self.company_id, shifted_date)
        else:
            self.date_from = self.date_to = False
