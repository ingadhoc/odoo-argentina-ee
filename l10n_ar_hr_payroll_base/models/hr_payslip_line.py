from odoo import fields, models

from .hr_payslip_input import UNITS


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    l10n_ar_quantity = fields.Float("Quantity (AR)", digits="Payroll", readonly=True)
    l10n_ar_unit = fields.Selection(UNITS, "Unit (AR)", readonly=True)
