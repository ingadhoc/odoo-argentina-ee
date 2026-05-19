from odoo import models


class AccountReturn(models.Model):
    _inherit = "account.return"

    def _check_suite_annual_closing(self, check_codes_to_ignore):
        checks = super()._check_suite_annual_closing(check_codes_to_ignore)

        # Move "Earnings Allocation" to the bottom of the list of checks
        earnings_checks = [c for c in checks if c.get("code") == "earnings_allocation"]
        if earnings_checks:
            checks = [c for c in checks if c.get("code") != "earnings_allocation"]
            checks.extend(earnings_checks)

        return checks
