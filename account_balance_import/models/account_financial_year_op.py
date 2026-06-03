from odoo import models


class FinancialYearOpeningWizard(models.TransientModel):
    _inherit = "account.financial.year.op"

    def write(self, vals):
        """Lo hacemos con sudo porque el usuario contabilidad / admin no tiene permiso para escribir en res.company
        Hay en odoo una suerte de inconsietencia porque este modelo esta justamente para contabilida / admin.
        Se replica en odoo si se usa el onboarding del tax return"""
        return super(FinancialYearOpeningWizard, self.sudo()).write(vals)

    def action_save_onboarding_fiscal_year(self):
        """Lo hacemos con sudo porque el usuario contabilidad / admin no tiene permiso para escribir en onboarding
        steps. Odoo tiene un sudo arriba pero no termina de funcionar, esto lo resuelve.
        Hay en odoo una suerte de inconsietencia porque este modelo esta justamente para contabilida / admin.
        """
        return super(FinancialYearOpeningWizard, self.sudo()).action_save_onboarding_fiscal_year()
