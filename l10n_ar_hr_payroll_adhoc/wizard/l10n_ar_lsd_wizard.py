from base64 import b64encode
from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import UserError


def _amount(value):
    return f"{round(abs(value) * 100):015d}"


def _code(record, width):
    return (record.code or "").zfill(width)[-width:] if record else "0" * width


class L10nArLsdWizard(models.TransientModel):
    _name = "l10n_ar.lsd.wizard"
    _description = "Digital payroll book"

    run_ids = fields.Many2many(
        "hr.payslip.run", string="Batches", default=lambda self: [(6, 0, self.env.context.get("active_ids", []))]
    )
    liquidation_number = fields.Integer("Settlement Number", default=1)
    lsd_file = fields.Binary("File", readonly=True, attachment=False)
    lsd_filename = fields.Char()

    def action_generate(self):
        slips = self.run_ids.slip_ids.filtered(lambda s: s.state in ("validated", "paid"))
        if not slips:
            raise UserError(self.env._("The batches have no validated payslips."))
        company = slips.company_id
        if len(company) > 1:
            raise UserError(self.env._("All batches must belong to the same company."))
        payment_date = self.run_ids.filtered("l10n_ar_payment_date")[:1].l10n_ar_payment_date
        if not payment_date:
            raise UserError(self.env._("Set the payment date on the batch."))
        period = max(slips.mapped("date_to"))
        cuit = company.partner_id.l10n_ar_vat or ""
        rows = [f"01{cuit}SJ{period:%Y%m}M{self.liquidation_number:05d}30{len(slips.employee_id):06d}"]
        for employee in slips.employee_id:
            rows += self._get_employee_rows(employee, slips.filtered(lambda s: s.employee_id == employee), payment_date)
        content = "\r\n".join(rows) + "\r\n"
        self.write(
            {
                "lsd_file": b64encode(content.encode("latin-1", "replace")),
                "lsd_filename": f"LSD_{cuit}_{period:%Y%m}.txt",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _get_employee_rows(self, employee, slips, payment_date):
        cuil = (employee.ssnid or "").replace("-", "")
        if len(cuil) != 11:
            raise UserError(self.env._("The CUIL (11 digits) of %s is missing.", employee.name))
        job = (employee.job_title or employee.job_id.name or "")[:50]
        cbu = employee.primary_bank_account_id.acc_number or ""
        rows = [
            f'02{cuil}{(employee.l10n_ar_file_number or ""):<10}{job:<50}{cbu:0>22}030'
            f'{payment_date:%Y%m%d}{payment_date:%Y%m%d}3'
        ]

        concepts = {}
        for line in slips._l10n_ar_lines(["REM", "NOREM", "INDEM", "DED"]):
            code = line.salary_rule_id.l10n_ar_lsd_code or line.code
            unit, qty = (
                ("%", abs(line.rate)) if line.rate != 100 else ("D", line.quantity) if line.quantity != 1 else (" ", 0)
            )
            concept = concepts.setdefault(code, {"unit": unit, "qty": 0.0, "total": 0.0})
            concept["qty"] = qty if unit == "%" else concept["qty"] + qty
            concept["total"] += line.total
        for code, c in concepts.items():
            rows.append(
                f'03{cuil}{code[:10]:<10}{round(c["qty"] * 100):05d}{c["unit"]}{_amount(c["total"])}'
                f'{"D" if c["total"] < 0 else "C"}      '
            )

        def total(codes):
            return sum(slips._l10n_ar_lines(codes).mapped("total"))

        rem = total(["REM"])
        capped = sum(slips.line_ids.filtered(lambda l: l.code == "JUB").mapped("amount"))
        days = sum(slips.line_ids.filtered(lambda l: l.code in ("BASIC", "FERIADO")).mapped("quantity"))
        bases = [rem + total(["NOREM", "INDEM"]), capped, rem, rem, capped, capped, 0, 0, rem, rem, 0, 0, rem, 0]
        spouse, children = employee._l10n_ar_family_at(max(slips.mapped("date_to")))
        rows.append(
            f"04{cuil}{int(spouse)}{children:02d}010"
            f'{slips.company_id.l10n_ar_employer_type or "1"}01 '
            f'{_code(employee.l10n_ar_condition_id, 2)}{_code(employee.l10n_ar_activity_id, 3)}'
            f'{_code(employee.l10n_ar_modality_id, 3)}{_code(employee.l10n_ar_casualty_id, 2)}'
            f'{_code(employee.l10n_ar_zone_id, 2)}{self._get_situations(employee, slips)}'
            f'{min(round(days), 99):02d}000{"0" * 10}{_code(employee.l10n_ar_health_insurance_id, 6)}00'
            f'{"0" * 90}{"".join(_amount(b) for b in bases)}'
        )
        return rows

    def _get_situations(self, employee, slips):
        """Up to three (situation code, start day) pairs for the month: the status history, broken by vacations."""
        date_from, date_to = min(slips.mapped("date_from")), max(slips.mapped("date_to"))
        if not employee._l10n_ar_situation_at(date_from):
            raise UserError(self.env._("Set the employment status history of %s.", employee.name))
        vacation_code = self.env.ref("l10n_ar_hr_payroll_adhoc.afip_code_situation_13")
        leaves = (
            self.env["hr.leave"]
            .sudo()
            .search(
                [
                    ("employee_id", "=", employee.id),
                    ("state", "=", "validate"),
                    ("holiday_status_id.work_entry_type_id.code", "=", "LEAVE720"),
                    ("request_date_from", "<=", date_to),
                    ("request_date_to", ">=", date_from),
                ]
            )
        )
        situations = []
        day = date_from
        while day <= date_to:
            on_vacation = any(leave.request_date_from <= day <= leave.request_date_to for leave in leaves)
            code = _code(vacation_code if on_vacation else employee._l10n_ar_situation_at(day), 2)
            if not situations or situations[-1][0] != code:
                situations.append((code, day.day))
            day += timedelta(days=1)
        if len(situations) > 3:
            raise UserError(
                self.env._("%s has more than three employment status changes in the period.", employee.name)
            )
        situations += [("00", 0)] * (3 - len(situations))
        return "".join(f"{code}{day:02d}" for code, day in situations)
