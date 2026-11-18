from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    porcentaje_exclusion = fields.Float(string="Porcentaje de exclusión")
    l10n_ar_sifere_excluded = fields.Boolean(
        string="Excluded from SIFERE",
        help="Suffered perceptions of this tax are not reported in the SIFERE TXT, because SIFERE Web already loads "
        "them by itself (e.g. SIRCIP).",
    )
