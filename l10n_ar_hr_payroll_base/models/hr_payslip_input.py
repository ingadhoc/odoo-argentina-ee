from odoo import fields, models

UNITS = [("D", "Days"), ("%", "Percentage")]


class HrPayslipInput(models.Model):
    _inherit = "hr.payslip.input"

    l10n_ar_quantity = fields.Float(
        "Quantity (AR)",
        digits="Payroll",
        help="Units shown next to the concept on the payslip and in the digital payroll book (days, percentage). "
        "Informative: the line amount is the input amount.",
    )
    l10n_ar_unit = fields.Selection(UNITS, "Unit (AR)")
