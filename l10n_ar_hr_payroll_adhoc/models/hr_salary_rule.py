from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    l10n_ar_lsd_code = fields.Char(
        "LSD Code",
        help="Concept code in the digital payroll book. If empty, the rule code is used.",
    )
