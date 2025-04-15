from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            if company.country_id.code == "AR":
                key = f"l10n_ar_edi.{company.id}_foreign_currency_payment"
                self.env["ir.config_parameter"].sudo().set_param(key, "account")
        return companies
