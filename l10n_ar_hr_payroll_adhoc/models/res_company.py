from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ar_employer_type = fields.Selection(
        [
            ("0", "Public administration"),
            ("1", "Decree 814/01, art. 2 sub. B"),
            ("2", "Temporary services, art. 2 sub. B"),
            ("4", "Decree 814/01, art. 2 sub. A"),
            ("5", "Temporary services, art. 2 sub. A"),
            ("7", "Private education"),
            ("8", "Decree 1212/03 - AFA clubs"),
        ],
        string="Employer Type (LSD)",
        default="1",
    )
