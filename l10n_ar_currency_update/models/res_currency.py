from odoo import _, models
from odoo.exceptions import UserError


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def write(self, vals):
        if "name" in vals:
            protected_to_check = self.filtered("l10n_ar_afip_code")
            renamed_protected = protected_to_check.filtered(lambda currency: currency.name != vals["name"])
            if renamed_protected:
                raise UserError(
                    _(
                        "Cannot change the name/code of %(currencies)s as it has an ARCA Code defined.\n"
                        "Doing so would affect both the automatic currency rate synchronization service and the electronic invoicing service.",
                        currencies=", ".join(renamed_protected.mapped("name")),
                    )
                )
        return super().write(vals)
