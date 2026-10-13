# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Argentina - Payroll (outside collective agreements)",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": "LCT payroll outside collective agreements: monthly, SAC, final settlement, "
    "single journal entry with payable per employee and digital payroll book",
    "countries": ["ar"],
    "website": "www.adhoc.com.ar",
    "author": "ADHOC SA",
    "license": "AGPL-3",
    "depends": [
        "l10n_ar",
        "hr_payroll_account",
        "hr_payroll_holidays",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_ar_afip_code_data.xml",
        "data/hr_rule_parameter_data.xml",
        "report/report_payslip.xml",
        "data/hr_payroll_data.xml",
        "data/hr_salary_rule_monthly_data.xml",
        "data/hr_salary_rule_sac_data.xml",
        "data/hr_salary_rule_final_data.xml",
        "data/mail_template_data.xml",
        "wizard/l10n_ar_lsd_wizard_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_payroll_views.xml",
        "views/res_company_views.xml",
    ],
    "demo": [
        "demo/l10n_ar_hr_payroll_demo.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
