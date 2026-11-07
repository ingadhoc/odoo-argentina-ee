import math
from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError

# Payslip salary breakdown: (employer rule codes, employee rule codes) per destination.
SALARY_COMPOSITION = {
    "union": ((), ()),
    "social_security": (("CJUB", "CFNE", "CFAM"), ("JUB",)),
    "health": (("COS", "CANSSAL"), ("OS",)),
    "inssjp": (("CLEY19032",), ("LEY19032",)),
    "art": (("ART", "ARTF"), ()),
    "life": (("SCVO",), ()),
}
CHART_COLORS = ["#4C72B0", "#C44E52", "#55A868", "#8172B2", "#64B5CD", "#DD8452", "#CCB974"]


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    l10n_ar_kind = fields.Selection(related="struct_id.l10n_ar_kind")
    l10n_ar_contribution_base = fields.Monetary(
        "Capped Contribution Base",
        help="Employee contribution base after the legal cap, for record 04 of the digital payroll book. "
        "Written by whoever computes the payslip: Odoo does not compute it.",
    )
    l10n_ar_situation_line_ids = fields.One2many(
        "l10n_ar.payroll.slip.situation",
        "payslip_id",
        "Employment Status",
        help="Employment status of each part of the period, for the digital payroll book. Recomputed with the "
        "payslip from the employee history and the work entries; it can be edited before validating.",
    )

    def _get_payslip_line_total(self, amount, quantity, rate, rule):
        # Round each line so categories, NET and the journal entry add up the same printed amounts.
        total = super()._get_payslip_line_total(amount, quantity, rate, rule)
        if self.struct_id.l10n_ar_kind:
            return self.currency_id.round(total)
        return total

    def compute_sheet(self):
        res = super().compute_sheet()
        for slip in self.filtered(lambda s: s.struct_id.l10n_ar_kind and s.state in ("draft", "verify")):
            slip.l10n_ar_situation_line_ids = [Command.clear()] + [
                Command.create({"day": day, "situation_id": situation.id})
                for situation, day in slip._l10n_ar_compute_situations()
            ]
        return res

    def _get_payslip_lines(self):
        """Carry the quantity and unit of each input to its payslip line, for the payslip and the payroll book.

        Odoo makes one line per input of a transcribed concept, in the order of the inputs, so they are matched
        by code and position.
        """
        line_vals = super()._get_payslip_lines()
        inputs_by_slip_code = defaultdict(list)
        for line in self.input_line_ids:
            inputs_by_slip_code[line.payslip_id.id, line.code].append(line)
        for vals in line_vals:
            pending = inputs_by_slip_code.get((vals["slip_id"], vals["code"]))
            if pending:
                line = pending.pop(0)
                vals.update({"l10n_ar_quantity": line.l10n_ar_quantity, "l10n_ar_unit": line.l10n_ar_unit})
        return line_vals

    # Employment status

    def _l10n_ar_compute_situations(self):
        """Return (situation, start day) for each change in the period.

        Each day takes the employee history; a work entry whose type has an employment status replaces it.
        """
        self.ensure_one()
        employee = self.employee_id.sudo()
        if not employee.l10n_ar_situation_ids:
            return []
        # Payroll users may lack Time Off rights; the status must come out anyway.
        work_entries = (
            self.env["hr.work.entry"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", employee.id),
                    ("state", "!=", "cancelled"),
                    ("date", ">=", self.date_from),
                    ("date", "<=", self.date_to),
                    ("work_entry_type_id.l10n_ar_situation_id", "!=", False),
                ],
                order="date",
            )
        )
        by_day = {}
        for entry in work_entries:
            by_day.setdefault(entry.date, entry.work_entry_type_id.l10n_ar_situation_id)
        situations = []
        day = self.date_from
        while day <= self.date_to:
            situation = by_day.get(day) or employee._l10n_ar_situation_at(day)
            if situation and (not situations or situations[-1][0] != situation):
                situations.append((situation, day.day))
            day += timedelta(days=1)
        return situations

    # Payslip PDF and email

    def _get_email_template(self):
        if self.struct_id.l10n_ar_kind:
            return self.env.ref("l10n_ar_hr_payroll_base.mail_template_payslip_ar", raise_if_not_found=False)
        return super()._get_email_template()

    def _l10n_ar_lines(self, category_codes):
        return self.line_ids.filtered(
            lambda l: l.total
            and l.salary_rule_id.appears_on_payslip
            and (l.category_id.code in category_codes or l.category_id.parent_id.code in category_codes)
        )

    def _l10n_ar_total(self, category_codes):
        return sum(self._l10n_ar_lines(category_codes).mapped("total"))

    def _l10n_ar_seniority_display(self):
        start = self.employee_id.sudo().l10n_ar_seniority_date or self.version_id.sudo().contract_date_start
        seniority = relativedelta(self.date_to, start) if start else relativedelta()
        return f"{seniority.years}a {seniority.months}m"

    def _l10n_ar_salary_composition(self):
        """Employer and employee amounts per destination, for the payslip breakdown."""
        self.ensure_one()

        def total(codes):
            return sum(abs(line.total) for line in self.line_ids if line.code in codes)

        result = {}
        for key, (employer_codes, employee_codes) in SALARY_COMPOSITION.items():
            employer, employee = total(employer_codes), total(employee_codes)
            result[key] = {"employer": employer, "employee": employee, "total": employer + employee}
        return result

    def _l10n_ar_employer_cost_chart(self):
        """Pie chart (inline SVG) of the total employer cost, with its legend."""
        self.ensure_one()
        composition = self._l10n_ar_salary_composition()
        labels = {
            "gross": self.env._("Taxable salary"),
            "social_security": self.env._("Social security"),
            "union": self.env._("Union cost"),
            "health": self.env._("Health insurance"),
            "inssjp": self.env._("PAMI"),
            "art": self.env._("ART"),
            "life": self.env._("Life insurance"),
        }
        amounts = {"gross": self._l10n_ar_total(["REM", "NOREM", "INDEM"])}
        amounts.update({key: composition[key]["total"] for key in labels if key != "gross"})
        raw = [(labels[key], amounts[key], color) for key, color in zip(labels, CHART_COLORS) if amounts[key] > 0]
        grand_total = sum(amount for _label, amount, _color in raw)
        if not grand_total:
            return {"svg": Markup(), "segments": []}
        # Largest remainder, so the legend percentages add up to 100.
        exact = [100.0 * amount / grand_total for _label, amount, _color in raw]
        pcts = [int(p) for p in exact]
        for i in sorted(range(len(exact)), key=lambda i: exact[i] - pcts[i], reverse=True)[: 100 - sum(pcts)]:
            pcts[i] += 1
        cx = cy = 50
        r = 48
        paths, segments, start = [], [], -90.0
        for (label, amount, color), pct in zip(raw, pcts):
            span = 360.0 * amount / grand_total
            end = start + span
            if len(raw) == 1:
                paths.append(Markup('<circle cx="%s" cy="%s" r="%s" fill="%s"/>') % (cx, cy, r, color))
            else:
                x1, y1 = cx + r * math.cos(math.radians(start)), cy + r * math.sin(math.radians(start))
                x2, y2 = cx + r * math.cos(math.radians(end)), cy + r * math.sin(math.radians(end))
                paths.append(
                    Markup('<path d="M%s,%s L%.2f,%.2f A%s,%s 0 %s 1 %.2f,%.2f Z" fill="%s"/>')
                    % (cx, cy, x1, y1, r, r, 1 if span > 180 else 0, x2, y2, color)
                )
            segments.append({"name": label, "pct": pct, "color": color})
            start = end
        svg = Markup(
            '<svg viewBox="0 0 100 100" width="100" height="100" xmlns="http://www.w3.org/2000/svg">%s</svg>'
        ) % Markup("").join(paths)
        return {"svg": svg, "segments": segments}

    # Accounting: one entry per batch, but payable lines per employee

    def _prepare_line_values(self, line, account, date, debit, credit):
        vals_list = super()._prepare_line_values(line, account, date, debit, credit)
        if self.company_id.batch_payroll_move_lines and line.salary_rule_id.employee_move_line:
            for vals in vals_list:
                vals["partner_id"] = self.employee_id.work_contact_id.id
        return vals_list

    def _get_existing_lines(self, line_ids, line, account_id, debit, credit):
        existing = super()._get_existing_lines(line_ids, line, account_id, debit, credit)
        if self.company_id.batch_payroll_move_lines and line.salary_rule_id.employee_move_line:
            partner_id = self.employee_id.work_contact_id.id
            return (vals for vals in existing if vals["partner_id"] == partner_id)
        return existing


class L10nArPayrollSlipSituation(models.Model):
    _name = "l10n_ar.payroll.slip.situation"
    _description = "Employment status of a payslip (digital payroll book)"
    _order = "payslip_id, day"

    payslip_id = fields.Many2one("hr.payslip", required=True, index=True, ondelete="cascade")
    day = fields.Integer("From Day", required=True)
    situation_id = fields.Many2one(
        "l10n_ar.payroll.afip.code", "Employment Status", required=True, domain=[("type", "=", "6")]
    )

    @api.constrains("day")
    def _check_day(self):
        for line in self:
            if not 1 <= line.day <= 31:
                raise ValidationError(self.env._("The day must be between 1 and 31."))
