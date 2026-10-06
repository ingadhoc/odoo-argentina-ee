import calendar
from datetime import datetime, time

import pytz
from dateutil.relativedelta import MO, relativedelta
from odoo import Command, fields
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

TZ = "America/Argentina/Buenos_Aires"
WAGE = 1000000.0


@tagged("post_install", "post_install_l10n", "-at_install")
class TestL10nArPayroll(TestPayslipValidationCommon):
    @classmethod
    @TestPayslipValidationCommon.setup_country("ar")
    @TestPayslipValidationCommon.setup_chart_template("ar_ri")
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref("base.ar"),
            structure=cls.ar("structure_monthly"),
            structure_type=cls.ar("structure_type_lct"),
            contract_fields={"wage": WAGE},
            tz=TZ,
        )
        cls._setup_accounting()
        # Previous full month, so the period is always closed and inside the parameter validity.
        cls.today = fields.Date.today()
        cls.date_from = cls.today + relativedelta(months=-1, day=1)
        cls.date_to = cls.date_from + relativedelta(day=31)

    @classmethod
    def ar(cls, xmlid):
        return cls.env.ref(f"l10n_ar_hr_payroll_adhoc.{xmlid}")

    @classmethod
    def _setup_accounting(cls):
        chart = cls.env["account.chart.template"]
        cls.payable_account = chart.ref("base_sueldos_a_pagar")
        social = chart.ref("base_suss_a_pagar")
        cls.journal = cls.env["account.journal"].create({"name": "Payroll", "code": "SUEL", "type": "general"})
        cls.env.company.batch_payroll_move_lines = True
        structures = cls.ar("structure_monthly") | cls.ar("structure_sac") | cls.ar("structure_final")
        structures.journal_id = cls.journal
        credit_by_code = {"ART": "base_art_a_pagar", "ARTF": "base_art_a_pagar", "SCVO": "base_seguro_de_vida_a_pagar"}
        debit_by_code = {
            "JUB": social,
            "LEY19032": social,
            "OS": social,
            "DEDUCTION": chart.ref("base_recupero_de_gastos"),
            "ATTACH_SALARY": chart.ref("base_embargos_a_depositar"),
        }
        for rule in structures.rule_ids:
            category = rule.category_id.code
            if category in ("REM", "SAC", "NOREM", "INDEM"):
                rule.account_debit = chart.ref("base_haberes_administrativos")
            elif rule.code == "NET":
                rule.account_credit = cls.payable_account
            elif rule.code in debit_by_code:
                rule.account_debit = debit_by_code[rule.code]
            elif category == "COMP":
                rule.account_debit = chart.ref("base_cargas_sociales_administrativos")
                rule.account_credit = chart.ref(credit_by_code.get(rule.code, "base_suss_a_pagar"))

    def _create_employee(self, name, start):
        return (
            self.env["hr.employee"]
            .sudo()
            .create(
                {
                    "name": name,
                    "company_id": self.env.company.id,
                    "resource_calendar_id": self.resource_calendar.id,
                    "structure_type_id": self.ar("structure_type_lct").id,
                    "contract_date_start": start,
                    "date_version": start,
                    "wage": WAGE,
                }
            )
            .sudo(False)
        )

    def _compute_slip(self, employee, structure, date_from, date_to, inputs=None):
        employee.version_id.generate_work_entries(date_from, date_to)
        slip = self.env["hr.payslip"].create(
            {
                "name": "Test Payslip",
                "employee_id": employee.id,
                "version_id": employee.version_id.id,
                "struct_id": structure.id,
                "date_from": date_from,
                "date_to": date_to,
                "input_line_ids": [
                    Command.create({"input_type_id": input_type.id, "amount": amount})
                    for input_type, amount in (inputs or {}).items()
                ],
            }
        )
        slip.compute_sheet()
        return slip

    def _local_day(self, day):
        tz = pytz.timezone(TZ)
        return [
            tz.localize(datetime.combine(day, moment)).astimezone(pytz.utc).replace(tzinfo=None)
            for moment in (time.min, time.max)
        ]

    def _totals(self, slip):
        return {line.code: line.total for line in slip.line_ids}

    def _assert_net_matches_lines(self, slip):
        """Invariant: the net salary is the sum of the printed concepts and deductions."""
        printed = slip._l10n_ar_total(["REM", "NOREM", "INDEM", "DED"])
        self.assertEqual(slip.currency_id.compare_amounts(slip.net_wage, printed), 0)

    def _assert_entry_is_clean(self, move):
        """Invariant: one balanced entry, without the adjustment line Odoo adds when lines do not add up."""
        self.assertEqual(len(move), 1)
        self.assertEqual(move.currency_id.compare_amounts(sum(move.line_ids.mapped("balance")), 0), 0)
        self.assertNotIn("Adjustment Entry", move.line_ids.mapped("name"))
        self.assertFalse(move.line_ids.filtered(lambda l: move.currency_id.is_zero(l.balance)))

    def _approve_vacation(self, date_from, date_to):
        vacation_type = self.ar("leave_type_vacation")
        allocation = (
            self.env["hr.leave.allocation"]
            .sudo()
            .create(
                {
                    "name": "Vacations",
                    "holiday_status_id": vacation_type.id,
                    "employee_id": self.employee.id,
                    "number_of_days": 14,
                    "date_from": date_from + relativedelta(month=1, day=1),
                }
            )
        )
        allocation.action_approve()
        self._generate_leave(date_from, date_to, vacation_type)

    def test_monthly_payslip(self):
        """Monthly payslip with two holidays, three vacation days and a manual deduction.

        Expected values from the "Valores esperados del recibo" table of the handoff, except the net:
        the table says 847,666.67 but its own lines add up to 847,666.66, which is what keeps the
        journal entry balanced.
        """
        monday = self.date_from + relativedelta(day=8, weekday=MO)
        holidays = [monday + relativedelta(days=1), monday + relativedelta(days=2)]
        self.env["resource.calendar.leaves"].create(
            [
                {
                    "name": "Holiday",
                    "calendar_id": self.resource_calendar.id,
                    "date_from": self._local_day(day)[0],
                    "date_to": self._local_day(day)[1],
                    "work_entry_type_id": self.ar("work_entry_type_holiday").id,
                }
                for day in holidays
            ]
        )
        self._approve_vacation(monday + relativedelta(days=7), monday + relativedelta(days=9))

        slip = self._compute_slip(
            self.employee,
            self.ar("structure_monthly"),
            self.date_from,
            self.date_to,
            {self.env.ref("hr_payroll.input_deduction"): 10000},
        )

        with self.subTest("days: holidays leave the basic salary, vacations stay"):
            quantities = {line.code: line.quantity for line in slip.line_ids}
            self.assertEqual(quantities["BASIC"], 28)
            self.assertEqual(quantities["FERIADO"], 2)
            self.assertEqual(quantities["PLUSVAC"], 3)
        with self.subTest("amounts of the handoff table"):
            self._validate_payslip(
                slip,
                {
                    "BASIC": 933333.33,
                    "FERIADO": 80000.0,
                    "PLUSVAC": 20000.0,
                    "JUB": -113666.67,
                    "LEY19032": -31000.0,
                    "OS": -31000.0,
                    "GROSS": 1033333.33,
                    "DEDUCTION": -10000.0,
                    "NET": 847666.66,
                    "CJUB": 111290.0,
                    "CLEY19032": 16430.0,
                    "CFNE": 9713.33,
                    "CANSSAL": 9300.0,
                    "CFAM": 48566.67,
                    "COS": 52700.0,
                    "ART": 6200.0,
                    "ARTF": 1839.0,
                    "SCVO": 424.62,
                },
            )
        with self.subTest("employer cost"):
            self.assertAlmostEqual(slip._l10n_ar_total(["COMP"]), 256463.62, places=2)
            self.assertAlmostEqual(slip._l10n_ar_total(["REM", "COMP"]), 1289796.95, places=2)
        with self.subTest("salary breakdown covers every contribution"):
            composition = slip._l10n_ar_salary_composition()
            employer = sum(group["employer"] for group in composition.values())
            employee = sum(group["employee"] for group in composition.values())
            self.assertAlmostEqual(employer, slip._l10n_ar_total(["COMP"]), places=2)
            self.assertAlmostEqual(employee, 175666.67, places=2)
            self.assertAlmostEqual(composition["health"]["employer"], 62000.0, places=2)
        self._assert_net_matches_lines(slip)

    def test_batch_entry_and_payments(self):
        """A batch of two employees with the same wage gives one entry and one payment per employee.

        Same amounts on purpose: it is the case where Odoo would merge the payable lines of both employees.
        """
        employees = self.employee | self._create_employee("Second Employee", self.date_from - relativedelta(years=1))
        run = self.env["hr.payslip.run"].create(
            {
                "name": "Batch",
                "company_id": self.env.company.id,
                "structure_id": self.ar("structure_monthly").id,
                "date_start": self.date_from,
                "date_end": self.date_to,
                "l10n_ar_payment_date": self.date_to + relativedelta(days=5),
            }
        )
        run.generate_payslips(employee_ids=employees.ids)
        run.slip_ids.action_payslip_done()
        move = run.slip_ids.move_id

        with self.subTest("one balanced entry for the whole batch"):
            self._assert_entry_is_clean(move)
            self.assertEqual(run.move_id, move)
        payable_lines = move.line_ids.filtered(lambda l: l.account_id == self.payable_account)
        with self.subTest("one payable line per employee, with the employee contact"):
            self.assertEqual(payable_lines.partner_id, employees.work_contact_id)
            self.assertEqual(len(payable_lines), 2)
            for slip in run.slip_ids:
                line = payable_lines.filtered(lambda l, s=slip: l.partner_id == s.employee_id.work_contact_id)
                self.assertEqual(line.currency_id.compare_amounts(line.credit, slip.net_wage), 0)

        move.action_post()
        action = run.action_l10n_ar_register_payments()
        wizard = (
            self.env["account.payment.register"]
            .with_context(**action["context"])
            .create(
                {
                    "journal_id": self.company_data["default_journal_bank"].id,
                    "payment_date": run.l10n_ar_payment_date,
                }
            )
        )
        payments = wizard._create_payments()
        with self.subTest("one payment per employee, reconciled with its line"):
            self.assertEqual(len(payments), 2)
            self.assertEqual(payments.partner_id, employees.work_contact_id)
            self.assertTrue(all(payable_lines.mapped("reconciled")))

    def test_sac_june(self):
        """The June SAC is half the best monthly gross of the semester, with half the contribution cap."""
        year = self.today.year if self.today.month > 6 else self.today.year - 1
        # Rule parameters loaded by the module start in 2026; keep the latest values valid for the semester.
        for parameter in self.env["hr.rule.parameter"].search([("code", "=like", "l10n_ar_%")]):
            versions = parameter.parameter_version_ids.sorted("date_from")
            if versions[0].date_from > fields.Date.to_date(f"{year}-01-01"):
                versions[-1].sudo().copy({"date_from": fields.Date.to_date(f"{year}-01-01")})
        april = fields.Date.to_date(f"{year}-04-01")
        self._compute_slip(self.employee, self.ar("structure_monthly"), april, april + relativedelta(day=31))
        may = self._compute_slip(
            self.employee,
            self.ar("structure_monthly"),
            april + relativedelta(months=1),
            april + relativedelta(months=1, day=31),
            {self.ar("input_rem"): 200000},
        )
        june = april + relativedelta(months=2)
        with self.subTest("May is the best month of the semester"):
            self.assertEqual(may.gross_wage, 1200000.0)

        sac = self._compute_slip(self.employee, self.ar("structure_sac"), june, june + relativedelta(day=31))
        self._validate_payslip(
            sac,
            {
                "SAC": 600000.0,
                "JUB": -66000.0,
                "LEY19032": -18000.0,
                "OS": -18000.0,
                "GROSS": 600000.0,
                "NET": 498000.0,
                "CJUB": 64620.0,
                "CLEY19032": 9540.0,
                "CFNE": 5640.0,
                "CANSSAL": 5400.0,
                "CFAM": 28200.0,
                "COS": 30600.0,
                "ART": 3600.0,
            },
        )
        self._assert_net_matches_lines(sac)

    def test_final_settlement(self):
        """Final settlement on day 15 after 2 years and 4 months, by resignation and by dismissal without cause.

        Both get the worked days, proportional SAC and unused vacations; only the dismissal adds notice,
        month integration and seniority severance (3 years: the 4 months count as one more). None of the
        severance concepts pays contributions.
        """
        departure = self.date_from + relativedelta(days=14)
        month_days = calendar.monthrange(departure.year, departure.month)[1]
        sem_start = departure + relativedelta(month=1 if departure.month <= 6 else 7, day=1)
        sem_days = ((sem_start + relativedelta(months=6)) - sem_start).days
        worked = (departure - sem_start).days + 1
        currency = self.env.company.currency_id
        integration = currency.round(WAGE / 30 * (month_days - 15))
        expected_sac = currency.round(WAGE / 2 / sem_days * worked)
        dismissal_lines = {
            "PREAV": WAGE,
            "PREAVSAC": currency.round(WAGE / 12),
            "IMD": integration,
            "IMDSAC": currency.round(integration / 12),
            "IATG": 3 * WAGE,
        }
        for dismissal in (False, True):
            with self.subTest(dismissal=dismissal):
                employee = self._create_employee(
                    f"Leaving Employee {dismissal}", departure - relativedelta(years=2, months=4)
                )
                employee.version_id.contract_date_end = departure
                slip = self._compute_slip(
                    employee,
                    self.ar("structure_final"),
                    self.date_from,
                    self.date_to,
                    {self.ar("input_vacation_days"): 7},
                )
                if dismissal:
                    slip.l10n_ar_dismissal = True
                    slip.compute_sheet()
                totals = self._totals(slip)
                expected = {
                    "BASIC": 500000.0,
                    "SAC": expected_sac,
                    "VNG": 280000.0,
                    "VNGSAC": 23333.33,
                    **(dismissal_lines if dismissal else {}),
                }
                for code, amount in expected.items():
                    self.assertEqual(currency.compare_amounts(totals.get(code, 0.0), amount), 0, code)
                if not dismissal:
                    self.assertFalse(set(dismissal_lines) & set(totals))
                rem = totals["BASIC"] + totals["SAC"]
                self.assertEqual(currency.compare_amounts(totals["JUB"], -currency.round(rem * 0.11)), 0)
                self._assert_net_matches_lines(slip)

    def test_lsd_employment_status(self):
        """Record 04 of the digital payroll book takes the status history and the family data in force.

        The status of each day comes from the history, vacations override it with code 12, and the
        result goes as up to three (code, start day) pairs; more changes in the month are rejected.
        """
        active = self.ar("afip_code_situation_8")
        unpaid = self.ar("afip_code_situation_1")
        monday = self.date_from + relativedelta(day=8, weekday=MO)
        self.employee.sudo().l10n_ar_situation_ids = [
            Command.create({"date_from": self.date_from - relativedelta(years=1), "situation_id": active.id})
        ]
        self._approve_vacation(monday, monday + relativedelta(days=2))
        slip = self._compute_slip(self.employee, self.ar("structure_monthly"), self.date_from, self.date_to)
        wizard = self.env["l10n_ar.lsd.wizard"].create({})

        with self.subTest("active, vacations and back to active"):
            expected = f"0101{12:02d}{monday.day:02d}01{monday.day + 3:02d}"
            self.assertEqual(wizard._get_situations(self.employee, slip), expected)
        with self.subTest("a fourth change in the month is rejected"):
            self.employee.sudo().l10n_ar_situation_ids = [
                Command.create({"date_from": monday + relativedelta(days=10), "situation_id": unpaid.id})
            ]
            with self.assertRaises(UserError):
                wizard._get_situations(self.employee, slip)
        with self.subTest("at most three status lines per month"):
            with self.assertRaises(ValidationError):
                self.employee.sudo().l10n_ar_situation_ids = [
                    Command.create({"date_from": monday + relativedelta(days=day), "situation_id": active.id})
                    for day in (11, 12, 13)
                ]
        with self.subTest("family data in force at the end of the period"):
            self.employee.sudo().l10n_ar_family_ids = [
                Command.create({"date_from": self.date_from, "kind": "spouse", "dependent": True}),
                Command.create(
                    {"date_from": self.date_from - relativedelta(years=1), "kind": "children", "children_count": 2}
                ),
                Command.create(
                    {"date_from": self.date_to + relativedelta(days=1), "kind": "children", "children_count": 3}
                ),
            ]
            self.assertEqual(self.employee._l10n_ar_family_at(self.date_to), (True, 2))
