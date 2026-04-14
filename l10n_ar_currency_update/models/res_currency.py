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
                        "No se puede cambiar el nombre/código de %(currencies)s ya que tiene un Código ARCA definido. \n"
                        "Hacerlo repercutiría tanto en el servicio de sincronización automática de tasa de cambio como en el servicio de facturación electrónica.",
                        currencies=", ".join(renamed_protected.mapped("name")),
                    )
                )
        return super().write(vals)
