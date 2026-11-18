from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    l10n_ar_lsd_code = fields.Char(
        "LSD Code",
        help="Concept code in the digital payroll book. If empty, the rule code is used.",
    )
    l10n_ar_lsd_code_second_half = fields.Char(
        "LSD Code (2nd Half)",
        help="Concept code in the digital payroll book for payslips from July to December, when it differs from "
        "the LSD Code (e.g. the SAC of each semester). If empty, the LSD Code is used.",
    )
