from odoo import fields, models


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    l10n_ar_kind = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("sac", "SAC"),
            ("final", "Final Settlement"),
        ],
        string="Settlement Kind (AR)",
    )
