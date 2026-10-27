import calendar
import math
from datetime import date

from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from odoo import fields, models

MONTH_DAYS = 30
VACATION_DIVISOR = 25
VACATION_CODE = "LEAVE720"
HOLIDAY_CODE = "LEAVE500"
TRIAL_PERIOD_MONTHS = 6
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
    l10n_ar_dismissal = fields.Boolean(
        "Dismissal Without Cause",
        help="Enables notice period, month integration and seniority severance.",
    )
    l10n_ar_notice_given = fields.Boolean("Notice Given")

    def _get_payslip_line_total(self, amount, quantity, rate, rule):
        # Round each line so categories, NET and the journal entry add up the same printed amounts.
        total = super()._get_payslip_line_total(amount, quantity, rate, rule)
        if self.struct_id.l10n_ar_kind:
            return self.currency_id.round(total)
        return total

    # Period and days

    def _l10n_ar_daily_wage(self):
        return self.version_id.wage / MONTH_DAYS

    def _l10n_ar_end_date(self):
        version = self.version_id.sudo()
        ends = [self.date_to, version.contract_date_end, self.employee_id.sudo().departure_date]
        return min(d for d in ends if d)

    def _l10n_ar_period_days(self):
        """Contract days in the payslip period, on a 30-day month basis."""
        start = max(self.date_from, self.version_id.sudo().contract_date_start or self.date_from)
        end = self._l10n_ar_end_date()
        if start == self.date_from and end == self.date_to:
            return MONTH_DAYS
        return min(max((end - start).days + 1, 0), MONTH_DAYS)

    def _l10n_ar_worked_days(self, code=None, paid=None):
        lines = self.worked_days_line_ids.filtered(lambda l: l.code != "OUT")
        if code:
            lines = lines.filtered(lambda l: l.code == code)
        if paid is not None:
            lines = lines.filtered(lambda l: l.is_paid == paid)
        return sum(lines.mapped("number_of_days"))

    def _l10n_ar_holiday_days(self):
        return self._l10n_ar_worked_days(HOLIDAY_CODE)

    def _l10n_ar_basic_days(self):
        return self._l10n_ar_period_days() - self._l10n_ar_worked_days(paid=False) - self._l10n_ar_holiday_days()

    def _l10n_ar_vacation_days(self):
        """Calendar days of approved vacations in the period (art. 151 LCT counts consecutive days)."""
        end = self._l10n_ar_end_date()
        # Payroll users may lack Time Off rights; vacations must count anyway.
        leaves = (
            self.env["hr.leave"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", self.employee_id.id),
                    ("state", "=", "validate"),
                    ("holiday_status_id.work_entry_type_id.code", "=", VACATION_CODE),
                    ("request_date_from", "<=", end),
                    ("request_date_to", ">=", self.date_from),
                ]
            )
        )
        return sum((min(l.request_date_to, end) - max(l.request_date_from, self.date_from)).days + 1 for l in leaves)

    def _l10n_ar_day_wage_25(self):
        """Day value for vacations (art. 155 LCT) and holidays: wage / 25."""
        return self.version_id.wage / VACATION_DIVISOR

    def _l10n_ar_vacation_plus(self):
        """Vacation days stay in the basic salary (wage / 30); this adds the difference up to wage / 25."""
        return self._l10n_ar_day_wage_25() - self._l10n_ar_daily_wage()

    # Contributions

    def _l10n_ar_contribution_base(self, categories):
        """Employee contribution base: remuneration capped by the legal maximum, half of it for the SAC."""
        cap = self._rule_parameter("l10n_ar_contribution_cap")
        sac = categories["SAC"]
        return min(categories["REM"] - sac, cap) + min(sac, cap / 2)

    # SAC

    def _l10n_ar_monthly_slips(self, date_from, date_to):
        return self.search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("struct_id.l10n_ar_kind", "=", "monthly"),
                ("state", "!=", "cancel"),
                ("date_from", ">=", date_from),
                ("date_to", "<=", date_to),
            ]
        )

    def _l10n_ar_best_monthly_gross(self, date_from, date_to):
        totals = {}
        for slip in self._l10n_ar_monthly_slips(date_from, date_to):
            month = slip.date_from.replace(day=1)
            totals[month] = totals.get(month, 0.0) + slip.gross_wage
        return max(totals.values(), default=0.0) or self.version_id.wage

    def _l10n_ar_sac(self):
        """Return (best monthly gross, semester days, worked days) for the semester of the payslip."""
        end = self._l10n_ar_end_date()
        first_half = end.month <= 6
        sem_start = date(end.year, 1 if first_half else 7, 1)
        sem_end = date(end.year, 6, 30) if first_half else date(end.year, 12, 31)
        start = max(sem_start, self.version_id.sudo().contract_date_start or sem_start)
        unpaid_types = (
            self.env["hr.payroll.structure"].search([("l10n_ar_kind", "=", "monthly")]).unpaid_work_entry_type_ids
        )
        unpaid_dates = set(
            self.env["hr.work.entry"]
            .search(
                [
                    ("employee_id", "=", self.employee_id.id),
                    ("work_entry_type_id", "in", unpaid_types.ids),
                    ("state", "!=", "cancelled"),
                    ("date", ">=", start),
                    ("date", "<=", end),
                ]
            )
            .mapped("date")
        )
        worked = max((end - start).days + 1 - len(unpaid_dates), 0)
        return self._l10n_ar_best_monthly_gross(sem_start, sem_end), (sem_end - sem_start).days + 1, worked

    # Final settlement

    def _l10n_ar_seniority(self):
        start = self.employee_id.sudo().l10n_ar_seniority_date or self.version_id.sudo().contract_date_start
        return relativedelta(self._l10n_ar_end_date(), start) if start else relativedelta()

    def _l10n_ar_pending_vacation_days(self, inputs):
        if "AR_VAC_DAYS" in inputs:
            return inputs["AR_VAC_DAYS"].amount
        leave_type = self.env["hr.leave.type"].sudo().search([("work_entry_type_id.code", "=", VACATION_CODE)], limit=1)
        return leave_type.with_context(employee_id=self.employee_id.id).virtual_remaining_leaves

    def _l10n_ar_notice_months(self):
        """Notice period of art. 231 LCT."""
        seniority = self._l10n_ar_seniority()
        if seniority.years * 12 + seniority.months < TRIAL_PERIOD_MONTHS:
            return 0.5
        return 1 if seniority.years < 5 else 2

    def _l10n_ar_month_integration_days(self):
        """Days left to complete the month of dismissal (art. 233 LCT)."""
        end = self._l10n_ar_end_date()
        return calendar.monthrange(end.year, end.month)[1] - end.day

    def _l10n_ar_seniority_years(self):
        """Years for art. 245 LCT: fractions over three months count as a full year, minimum one."""
        seniority = self._l10n_ar_seniority()
        return max(seniority.years + (1 if seniority.months >= 3 else 0), 1)

    def _l10n_ar_severance_wage(self):
        end = self._l10n_ar_end_date()
        return self._l10n_ar_best_monthly_gross(end - relativedelta(years=1), end)

    # Payslip PDF and email

    def _get_email_template(self):
        if self.struct_id.l10n_ar_kind:
            return self.env.ref("l10n_ar_hr_payroll_adhoc.mail_template_payslip_ar", raise_if_not_found=False)
        return super()._get_email_template()

    def _l10n_ar_lines(self, category_codes):
        return self.line_ids.filtered(
            lambda l: l.total
            and l.salary_rule_id.appears_on_payslip
            and (l.category_id.code in category_codes or l.category_id.parent_id.code in category_codes)
        )

    def _l10n_ar_total(self, category_codes):
        return sum(self._l10n_ar_lines(category_codes).mapped("total"))

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

    def _l10n_ar_seniority_display(self):
        seniority = self._l10n_ar_seniority()
        return f"{seniority.years}a {seniority.months}m"

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
