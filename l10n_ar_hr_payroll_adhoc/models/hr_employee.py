from odoo import api, fields, models
from odoo.exceptions import ValidationError

MAX_SITUATIONS_PER_MONTH = 3


def _afip_code(string, code_type):
    return fields.Many2one(
        "l10n_ar.payroll.afip.code", string=string, domain=[("type", "=", code_type)], groups="hr.group_hr_user"
    )


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_ar_file_number = fields.Char("File Number", size=10, groups="hr.group_hr_user", copy=False)
    l10n_ar_seniority_date = fields.Date(
        "Recognized Start Date",
        groups="hr.group_hr_user",
        help="Base for seniority. If empty, the contract start date is used.",
    )
    l10n_ar_condition_id = _afip_code("Condition", "1")
    l10n_ar_activity_id = _afip_code("Activity", "2")
    l10n_ar_modality_id = _afip_code("Hiring Modality", "3")
    l10n_ar_casualty_id = _afip_code("Casualty", "4")
    l10n_ar_zone_id = _afip_code("Zone", "5")
    l10n_ar_health_insurance_id = _afip_code("Health Insurance", "7")
    l10n_ar_situation_ids = fields.One2many(
        "l10n_ar.payroll.situation", "employee_id", "Employment Status History", groups="hr.group_hr_user"
    )
    l10n_ar_family_ids = fields.One2many(
        "l10n_ar.payroll.family", "employee_id", "Family Information", groups="hr.group_hr_user"
    )

    def _l10n_ar_situation_at(self, day):
        """Employment status in force on the given day, from the history."""
        self.ensure_one()
        lines = self.sudo().l10n_ar_situation_ids.filtered(lambda l: l.date_from <= day)
        return lines.sorted("date_from")[-1:].situation_id

    def _l10n_ar_family_at(self, day):
        """Return (dependent spouse, dependent children) in force on the given day."""
        self.ensure_one()
        lines = self.sudo().l10n_ar_family_ids.filtered(lambda l: l.date_from <= day).sorted("date_from")
        spouse = lines.filtered(lambda l: l.kind == "spouse")[-1:]
        children = lines.filtered(lambda l: l.kind == "children")[-1:]
        return bool(spouse.dependent), children.children_count


class L10nArPayrollSituation(models.Model):
    _name = "l10n_ar.payroll.situation"
    _description = "Employment status history (digital payroll book)"
    _order = "employee_id, date_from"

    employee_id = fields.Many2one("hr.employee", required=True, index=True, ondelete="cascade")
    situation_id = fields.Many2one(
        "l10n_ar.payroll.afip.code", "Employment Status", required=True, domain=[("type", "=", "6")]
    )
    date_from = fields.Date("From", required=True)

    @api.constrains("employee_id", "date_from")
    def _check_situations_per_month(self):
        for line in self:
            month = line.date_from.replace(day=1)
            same_month = line.employee_id.l10n_ar_situation_ids.filtered(
                lambda l, m=month: l.date_from.replace(day=1) == m
            )
            if len(same_month) > MAX_SITUATIONS_PER_MONTH:
                raise ValidationError(
                    self.env._(
                        "%(employee)s can have at most three employment status changes per month.",
                        employee=line.employee_id.name,
                    )
                )


class L10nArPayrollFamily(models.Model):
    _name = "l10n_ar.payroll.family"
    _description = "Family information history (digital payroll book)"
    _order = "employee_id, date_from"

    employee_id = fields.Many2one("hr.employee", required=True, index=True, ondelete="cascade")
    kind = fields.Selection([("spouse", "Spouse"), ("children", "Children")], "Type", required=True)
    date_from = fields.Date("From", required=True)
    dependent = fields.Boolean("Dependent Spouse")
    children_count = fields.Integer("Dependent Children")
