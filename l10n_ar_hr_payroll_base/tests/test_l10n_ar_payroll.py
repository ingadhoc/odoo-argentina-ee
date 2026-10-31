from base64 import b64decode

from dateutil.relativedelta import MO, relativedelta
from odoo import Command, fields
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

TZ = "America/Argentina/Buenos_Aires"
WAGE = 1000000.0
# The September case of the demo: amounts computed outside Odoo, as the skill writes them.
CONCEPTS = {
    "BASIC": (933333.33, 28, "D"),
    "FERIADO": (80000.0, 2, "D"),
    "PLUSVAC": (20000.0, 3, "D"),
    "JUB": (113666.67, 11, "%"),
    "LEY19032": (31000.0, 3, "%"),
    "OS": (31000.0, 3, "%"),
    "DEDUCTION": (10000.0, 0, False),
    "CJUB": (111290.0, 0, False),
    "CLEY19032": (16430.0, 0, False),
    "CFNE": (9713.33, 0, False),
    "CANSSAL": (9300.0, 0, False),
    "CFAM": (48566.67, 0, False),
    "COS": (52700.0, 0, False),
    "ART": (6200.0, 0, False),
    "ARTF": (1839.0, 0, False),
    "SCVO": (424.62, 0, False),
}
REMUNERATION = 1033333.33


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
        # Previous full month, so the period is always closed.
        cls.today = fields.Date.today()
        cls.date_from = cls.today + relativedelta(months=-1, day=1)
        cls.date_to = cls.date_from + relativedelta(day=31)
        cls.active = cls.ar("afip_code_situation_8")
        cls.employee.sudo().write(
            {
                "ssnid": "20301234563",
                "l10n_ar_file_number": "0001",
                "l10n_ar_situation_ids": [
                    Command.create({"date_from": cls.date_from - relativedelta(years=1), "situation_id": cls.active.id})
                ],
            }
        )

    @classmethod
    def ar(cls, xmlid):
        return cls.env.ref(f"l10n_ar_hr_payroll_base.{xmlid}")

    @classmethod
    def _setup_accounting(cls):
        chart = cls.env["account.chart.template"]
        cls.payable_account = chart.ref("base_sueldos_a_pagar")
        cls.journal = cls.env["account.journal"].create({"name": "Payroll", "code": "SUEL", "type": "general"})
        cls.env.company.batch_payroll_move_lines = True
        structures = cls.ar("structure_monthly") | cls.ar("structure_sac") | cls.ar("structure_final")
        structures.journal_id = cls.journal
        credit_by_code = {"ART": "base_art_a_pagar", "ARTF": "base_art_a_pagar", "SCVO": "base_seguro_de_vida_a_pagar"}
        for rule in structures.rule_ids:
            category = rule.category_id.code
            if category in ("REM", "SAC", "NOREM", "INDEM"):
                rule.account_debit = chart.ref("base_haberes_administrativos")
            elif rule.code == "NET":
                rule.account_credit = cls.payable_account
            elif category == "DED":
                rule.account_debit = chart.ref("base_suss_a_pagar")
            elif category == "COMP":
                rule.account_debit = chart.ref("base_cargas_sociales_administrativos")
                rule.account_credit = chart.ref(credit_by_code.get(rule.code, "base_suss_a_pagar"))

    def _input(self, code, amount, quantity=0.0, unit=False, name=False):
        xmlid = "hr_payroll.input_deduction" if code == "DEDUCTION" else f"l10n_ar_hr_payroll_base.input_{code.lower()}"
        return Command.create(
            {
                "input_type_id": self.env.ref(xmlid).id,
                "amount": amount,
                "l10n_ar_quantity": quantity,
                "l10n_ar_unit": unit,
                **({"name": name} if name else {}),
            }
        )

    def _write_concepts(self, slips, concepts=None, base=REMUNERATION):
        """What the skill does: write the amounts and the capped base, then recompute the payslip."""
        concepts = concepts or CONCEPTS
        slips.write(
            {
                "l10n_ar_contribution_base": base,
                "input_line_ids": [self._input(code, *values) for code, values in concepts.items()],
            }
        )
        slips.compute_sheet()

    def _create_run(self, employees):
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
        return run

    def test_transcription(self):
        """Odoo computes nothing: each concept is the amount written on the payslip, with the sign of its category."""
        slip = self._create_run(self.employee).slip_ids
        with self.subTest("without inputs there are no concepts"):
            slip.compute_sheet()
            self.assertFalse(slip._l10n_ar_lines(["REM", "NOREM", "INDEM", "DED", "COMP"]))
            self.assertEqual(slip.net_wage, 0)

        self._write_concepts(slip, {**CONCEPTS, "GAN": (25000.0, 0, False)})
        self._validate_payslip(
            slip,
            {
                **{code: amount for code, (amount, _qty, _unit) in CONCEPTS.items()},
                "JUB": -113666.67,
                "LEY19032": -31000.0,
                "OS": -31000.0,
                "DEDUCTION": -10000.0,
                "GAN": -25000.0,
                "GROSS": REMUNERATION,
                "NET": 822666.66,
            },
        )
        lines = {line.code: line for line in slip.line_ids}
        with self.subTest("quantity and unit go from the input to the line"):
            self.assertEqual((lines["BASIC"].l10n_ar_quantity, lines["BASIC"].l10n_ar_unit), (28, "D"))
            self.assertEqual((lines["JUB"].l10n_ar_quantity, lines["JUB"].l10n_ar_unit), (11, "%"))
        with self.subTest("the net is the sum of the printed concepts"):
            printed = slip._l10n_ar_total(["REM", "NOREM", "INDEM", "DED"])
            self.assertEqual(slip.currency_id.compare_amounts(slip.net_wage, printed), 0)
            self.assertAlmostEqual(slip._l10n_ar_total(["COMP"]), 256463.62, places=2)
        with self.subTest("a negative withholding is a refund"):
            slip.input_line_ids.filtered(lambda l: l.code == "GAN").amount = -5000.0
            slip.compute_sheet()
            self.assertEqual(slip.line_ids.filtered(lambda l: l.code == "GAN").total, 5000.0)
        with self.subTest("two inputs of the same concept make two lines"):
            slip.input_line_ids = [self._input("AR_REM", 1000.0, name="Bonus"), self._input("AR_REM", 500.0)]
            slip.compute_sheet()
            extra = slip.line_ids.filtered(lambda l: l.code == "AR_REM")
            self.assertEqual(sorted(extra.mapped("total")), [500.0, 1000.0])
            self.assertIn("Bonus", extra.mapped("name"))

    def test_batch_entry_and_payments(self):
        """A batch of two employees with the same amounts gives one entry and one payment per employee.

        Same amounts on purpose: it is the case where Odoo would merge the payable lines of both employees.
        """
        second = (
            self.env["hr.employee"]
            .sudo()
            .create(
                {
                    "name": "Second Employee",
                    "company_id": self.env.company.id,
                    "resource_calendar_id": self.resource_calendar.id,
                    "structure_type_id": self.ar("structure_type_lct").id,
                    "contract_date_start": self.date_from - relativedelta(years=1),
                    "date_version": self.date_from - relativedelta(years=1),
                    "wage": WAGE,
                }
            )
            .sudo(False)
        )
        employees = self.employee | second
        run = self._create_run(employees)
        self._write_concepts(run.slip_ids)
        run.slip_ids.action_payslip_done()
        move = run.slip_ids.move_id

        with self.subTest("one balanced entry for the whole batch"):
            self.assertEqual(len(move), 1)
            self.assertEqual(move.currency_id.compare_amounts(sum(move.line_ids.mapped("balance")), 0), 0)
            self.assertNotIn("Adjustment Entry", move.line_ids.mapped("name"))
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

    def test_employment_status(self):
        """The employment status of each day is the history, unless the work entry type carries its own.

        Vacations are mapped to code 12, so active, vacations and back to active make three lines on the payslip.
        """
        monday = self.date_from + relativedelta(day=8, weekday=MO)
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
                    "date_from": self.date_from + relativedelta(month=1, day=1),
                }
            )
        )
        allocation.action_approve()
        self._generate_leave(monday, monday + relativedelta(days=2), vacation_type)
        self.employee.version_id.generate_work_entries(self.date_from, self.date_to)
        slip = self._create_run(self.employee).slip_ids
        slip.compute_sheet()
        wizard = self.env["l10n_ar.lsd.wizard"].create({})

        with self.subTest("active, vacations and back to active"):
            self.assertEqual(
                [(line.situation_id.code, line.day) for line in slip.l10n_ar_situation_line_ids],
                [("1", 1), ("12", monday.day), ("1", monday.day + 3)],
            )
            expected = f"0101{12:02d}{monday.day:02d}01{monday.day + 3:02d}"
            self.assertEqual(wizard._get_situations(self.employee, slip), expected)
        with self.subTest("a fourth change, edited by hand on the payslip, is rejected by the payroll book"):
            slip.l10n_ar_situation_line_ids = [
                Command.create({"day": monday.day + 10, "situation_id": self.ar("afip_code_situation_1").id})
            ]
            with self.assertRaises(UserError):
                wizard._get_situations(self.employee, slip)
        with self.subTest("at most three status lines per month in the history"):
            with self.assertRaises(ValidationError):
                self.employee.sudo().l10n_ar_situation_ids = [
                    Command.create({"date_from": monday + relativedelta(days=day), "situation_id": self.active.id})
                    for day in (11, 12, 13, 14)
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

    def test_lsd_file(self):
        """The payroll book file takes the concepts, their units and the capped base as they were written."""
        run = self._create_run(self.employee)
        slip = run.slip_ids
        self._write_concepts(slip, base=0)
        slip.action_payslip_done()
        wizard = self.env["l10n_ar.lsd.wizard"].create({"run_ids": [Command.set(run.ids)]})

        with self.subTest("without the capped base the file is not generated"):
            with self.assertRaises(UserError):
                wizard.action_generate()

        # Below the remuneration on purpose, to tell the capped bases from the full ones.
        slip.l10n_ar_contribution_base = 900000.0
        wizard.action_generate()
        rows = b64decode(wizard.lsd_file).decode("latin-1").split("\r\n")
        concepts = {row[13:23].strip(): row for row in rows if row.startswith("03")}
        with self.subTest("record 03: units of days and percentages, debit for deductions"):
            self.assertEqual(concepts["BASIC"][23:29], "02800D")
            self.assertEqual(concepts["JUB"][23:29], "01100%")
            self.assertEqual(concepts["JUB"][29:44], f"{11366667:015d}")
            self.assertEqual(concepts["JUB"][44], "D")
            self.assertEqual(concepts["DEDUCTION"][23:29], "00000 ")
            self.assertNotIn("CJUB", concepts)
        record_04 = next(row for row in rows if row.startswith("04"))
        with self.subTest("record 04: the capped base goes to the capped bases, the remuneration to the rest"):
            self.assertEqual(record_04.count(f"{90000000:015d}"), 3)
            self.assertEqual(record_04.count(f"{103333333:015d}"), 6)
