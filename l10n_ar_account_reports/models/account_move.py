from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        """Hacemos que algunos reportes argentinos queden en borrador"""
        if (
            self._context.get("post_from_tax_return")
            and self.company_id.country_id.code == "AR"
            and self.closing_return_id.type_id
            in [
                self.env.ref("l10n_ar_account_reports.ar_sifere_iibb_return_type"),
                self.env.ref("l10n_ar_reports.ar_tax_return_type"),
            ]
        ):
            return False
        return super().action_post()
