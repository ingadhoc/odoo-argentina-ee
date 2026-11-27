from datetime import date, datetime

from odoo import Command, api, models

TZ = "America/Argentina/Buenos_Aires"


class L10nArPayrollDemo(models.AbstractModel):
    _name = "l10n_ar.payroll.demo"
    _description = "Argentine payroll demo"

    @api.model
    def _load_demo(self):
        """September 2026 for Distribuidora SRL - Sueldos: setup, payslip with the amounts written as the skill does, entry, payment, email and LSD file."""
        company = self.env.ref("l10n_ar_hr_payroll_base.demo_company_distribuidora")
        self = self.with_company(company).with_context(allowed_company_ids=company.ids, tracking_disable=True)
        # _load instead of try_loading: no demo entries for this company and no warning during install.
        self.env["account.chart.template"]._load("ar_ri", company, install_demo=False)
        self._demo_setup_accounting(company)
        employee = self._demo_create_employee(company)
        self._demo_create_time_off(company, employee)
        run = self._demo_run_payroll(company, employee)
        self._demo_pay(company, run)
        self._demo_lsd(run)

    def _demo_setup_accounting(self, company):
        chart = self.env["account.chart.template"]
        accounts = {
            "salary": chart.ref("base_haberes_administrativos"),
            "charges": chart.ref("base_cargas_sociales_administrativos"),
            "payable": chart.ref("base_sueldos_a_pagar"),
            "social": chart.ref("base_suss_a_pagar"),
            "art": chart.ref("base_art_a_pagar"),
            "life": chart.ref("base_seguro_de_vida_a_pagar"),
            "recovery": chart.ref("base_recupero_de_gastos"),
            "liens": chart.ref("base_embargos_a_depositar"),
            "withholding": chart.ref("ri_retencion_ganancias_aplicada"),
        }
        journal = self.env["account.journal"].create(
            {"name": "Sueldos y Jornales", "code": "SUEL", "type": "general", "company_id": company.id}
        )
        company.batch_payroll_move_lines = True
        credit_by_code = {"ART": "art", "ARTF": "art", "SCVO": "life"}
        debit_by_code = {
            "JUB": "social",
            "LEY19032": "social",
            "OS": "social",
            "DEDUCTION": "recovery",
            "ATTACH_SALARY": "liens",
            "GAN": "withholding",
        }
        structures = self.env["hr.payroll.structure"].search([("l10n_ar_kind", "!=", False)])
        structures.journal_id = journal
        for rule in structures.rule_ids:
            category = rule.category_id.code
            if category in ("REM", "SAC", "NOREM", "INDEM"):
                rule.account_debit = accounts["salary"]
            elif rule.code == "NET":
                rule.account_credit = accounts["payable"]
            elif rule.code in debit_by_code:
                rule.account_debit = accounts[debit_by_code[rule.code]]
            elif category == "COMP":
                rule.account_debit = accounts["charges"]
                rule.account_credit = accounts[credit_by_code.get(rule.code, "social")]

    def _demo_create_employee(self, company):
        def afip(code_type, name):
            return (
                self.env["l10n_ar.payroll.afip.code"]
                .search([("type", "=", code_type), ("name", "ilike", name)], limit=1)
                .id
            )

        company.resource_calendar_id.tz = TZ
        # Spanish payslip when the language is installed.
        lang = self.env["res.lang"].search([("code", "=", "es_419")], limit=1).code
        employee = self.env["hr.employee"].create(
            {
                **({"lang": lang} if lang else {}),
                "name": "Colaborador Adhoc",
                "company_id": company.id,
                "work_email": "colaborador.adhoc@example.com",
                "job_title": "Analista administrativo",
                "tz": TZ,
                "ssnid": "20301234563",
                "l10n_ar_file_number": "0001",
                "l10n_ar_seniority_date": date(2024, 3, 1),
                "l10n_ar_condition_id": afip("1", "Servicios Comunes"),
                "l10n_ar_activity_id": afip("2", "No clasificados"),
                "l10n_ar_modality_id": afip("3", "Tiempo completo indeterminado"),
                "l10n_ar_casualty_id": afip("4", "No Incapacitado"),
                "l10n_ar_zone_id": self.env.ref("l10n_ar_hr_payroll_base.afip_code_zone_177").id,
                "l10n_ar_health_insurance_id": self.env.ref("l10n_ar_hr_payroll_base.afip_code_health_226").id,
                "l10n_ar_situation_ids": [
                    Command.create(
                        {
                            "date_from": date(2024, 3, 1),
                            "situation_id": self.env.ref("l10n_ar_hr_payroll_base.afip_code_situation_8").id,
                        }
                    )
                ],
                "contract_date_start": date(2024, 3, 1),
                "date_version": date(2024, 3, 1),
                "wage": 1000000,
                "wage_type": "monthly",
                "structure_type_id": self.env.ref("l10n_ar_hr_payroll_base.structure_type_lct").id,
                "resource_calendar_id": company.resource_calendar_id.id,
            }
        )
        partner = employee.work_contact_id
        partner.property_account_payable_id = self.env["account.chart.template"].ref("base_sueldos_a_pagar")
        bank = self.env["res.partner.bank"].create(
            {"acc_number": "0720123900001234567891", "partner_id": partner.id, "allow_out_payment": True}
        )
        employee.bank_account_ids = [Command.set(bank.ids)]
        self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": employee.name,
                "login": partner.email,
                "password": "colaborador.adhoc",
                "partner_id": partner.id,
                "company_id": company.id,
                "company_ids": [Command.set(company.ids)],
                "group_ids": [Command.set(self.env.ref("base.group_portal").ids)],
            }
        )
        return employee

    def _demo_create_time_off(self, company, employee):
        holiday_type = self.env.ref("l10n_ar_hr_payroll_base.work_entry_type_holiday")
        # Global leaves are stored in UTC: 03:00 UTC is midnight in Argentina.
        self.env["resource.calendar.leaves"].create(
            [
                {
                    "name": "Feriado (demo)",
                    "company_id": company.id,
                    "calendar_id": company.resource_calendar_id.id,
                    "date_from": datetime(2026, 9, day, 3, 0),
                    "date_to": datetime(2026, 9, day + 1, 2, 59, 59),
                    "work_entry_type_id": holiday_type.id,
                }
                for day in (14, 15)
            ]
        )
        vacation_type = self.env.ref("l10n_ar_hr_payroll_base.leave_type_vacation")
        allocation = self.env["hr.leave.allocation"].create(
            {
                "name": "Vacaciones 2026",
                "holiday_status_id": vacation_type.id,
                "employee_id": employee.id,
                "number_of_days": 14,
                "date_from": date(2026, 1, 1),
            }
        )
        allocation.action_approve()
        leave = self.env["hr.leave"].create(
            {
                "holiday_status_id": vacation_type.id,
                "employee_id": employee.id,
                "request_date_from": date(2026, 9, 21),
                "request_date_to": date(2026, 9, 23),
            }
        )
        leave.action_approve()

    def _demo_run_payroll(self, company, employee):
        run = self.env["hr.payslip.run"].create(
            {
                "name": "Sueldos septiembre 2026",
                "company_id": company.id,
                "structure_id": self.env.ref("l10n_ar_hr_payroll_base.structure_monthly").id,
                "date_start": date(2026, 9, 1),
                "date_end": date(2026, 9, 30),
                "l10n_ar_payment_date": date(2026, 10, 5),
                "l10n_ar_contribution_date": date(2026, 9, 10),
            }
        )
        run.generate_payslips(employee_ids=employee.ids)
        # What the skill writes: the amounts of the September case, computed outside Odoo.
        run.slip_ids.write({"l10n_ar_contribution_base": 1033333.33, "input_line_ids": self._demo_inputs()})
        run.slip_ids.compute_sheet()
        run.slip_ids.action_payslip_done()
        run.slip_ids.move_id.action_post()
        return run

    def _demo_inputs(self):
        def concept(code, amount, quantity=0.0, unit=False, name=False):
            xmlid = (
                "hr_payroll.input_deduction" if code == "DEDUCTION" else f"l10n_ar_hr_payroll_base.input_{code.lower()}"
            )
            return Command.create(
                {
                    "input_type_id": self.env.ref(xmlid).id,
                    "amount": amount,
                    "l10n_ar_quantity": quantity,
                    "l10n_ar_unit": unit,
                    **({"name": name} if name else {}),
                }
            )

        return [
            concept("BASIC", 933333.33, 28, "D"),
            concept("FERIADO", 80000.0, 2, "D"),
            concept("PLUSVAC", 20000.0, 3, "D"),
            concept("JUB", 113666.67, 11, "%"),
            concept("LEY19032", 31000.0, 3, "%"),
            concept("OS", 31000.0, 3, "%"),
            concept("DEDUCTION", 10000.0, name="Internet"),
            concept("CJUB", 111290.0),
            concept("CLEY19032", 16430.0),
            concept("CFNE", 9713.33),
            concept("CANSSAL", 9300.0),
            concept("CFAM", 48566.67),
            concept("COS", 52700.0),
            concept("ART", 6200.0),
            concept("ARTF", 1839.0),
            concept("SCVO", 424.62),
        ]

    def _demo_pay(self, company, run):
        action = run.action_l10n_ar_register_payments()
        # The chart of accounts does not always create a bank journal.
        bank_journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", company.id)], limit=1
        ) or self.env["account.journal"].create(
            {"name": "Banco", "code": "BNK1", "type": "bank", "company_id": company.id}
        )
        wizard = (
            self.env["account.payment.register"]
            .with_context(**action["context"])
            .create({"journal_id": bank_journal.id, "payment_date": run.l10n_ar_payment_date})
        )
        wizard.action_create_payments()
        run.slip_ids.filtered(lambda s: s.state != "paid").action_payslip_paid()

    def _demo_lsd(self, run):
        wizard = self.env["l10n_ar.lsd.wizard"].create({"run_ids": [Command.set(run.ids)]})
        wizard.action_generate()
        self.env["ir.attachment"].create(
            {"name": wizard.lsd_filename, "datas": wizard.lsd_file, "res_model": run._name, "res_id": run.id}
        )
