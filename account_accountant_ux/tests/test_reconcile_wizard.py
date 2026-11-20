# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestReconcileWizardCompanyCurrency(AccountTestInvoicingCommon):
    """Regresión: con reconcile_on_company_currency activo el wizard de conciliación
    debe proponer el write-off en moneda de compañía con el importe exacto, sin
    convertir a moneda secundaria y de vuelta (lo que introduce error de redondeo).

    Caso real (ticket 120245): débito 1.210 vs crédito 700/0,50 en moneda secundaria
    → diferencia 510 en moneda de compañía. Sin el fix el wizard elige la moneda
    secundaria y propone 0,36 × 1400 = 504 en lugar de 510 (verificado).

    Nota: la moneda de compañía del entorno de test (AccountTestInvoicingCommon) es
    USD, así que usamos EUR como la moneda secundaria "cara" que en producción
    representa el USD frente al ARS. La tasa 1 EUR = 1400 (moneda de compañía)
    reproduce el mismo factor de redondeo del caso real.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        # Las compañías argentinas exigen redondeo global (constraint de
        # saas_client_l10n_ar); lo seteamos junto con el país para no pegar
        # contra un estado intermedio inválido.
        cls.company.write(
            {
                "country_id": cls.env.ref("base.ar").id,
                "tax_calculation_rounding_method": "round_globally",
            }
        )
        cls.company.reconcile_on_company_currency = True
        cls.company_currency = cls.company_data["currency"]
        # rate = unidades de moneda secundaria por unidad de compañía → 1/1400
        # significa 1 EUR = 1400 (moneda de compañía).
        cls.foreign_currency = cls.setup_other_currency("EUR", rates=[("2016-01-01", 1 / 1400)])
        cls.receivable = cls.company_data["default_account_receivable"]
        cls.receivable.currency_id = False
        cls.date = fields.Date.from_string("2016-01-01")

    def _receivable_line(self, balance, currency, amount_currency):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": self.date,
                "journal_id": self.company_data["default_journal_misc"].id,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": self.receivable.id,
                            "balance": balance,
                            "currency_id": currency.id,
                            "amount_currency": amount_currency,
                        }
                    ),
                    Command.create(
                        {
                            "account_id": self.company_data["default_account_revenue"].id,
                            "balance": -balance,
                            "currency_id": currency.id,
                            "amount_currency": -amount_currency,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        return move.line_ids.filtered(lambda l: l.account_id == self.receivable)

    def test_wizard_proposes_write_off_in_company_currency(self):
        """El wizard debe proponer 510 en moneda de compañía, no 504 (0,36 × 1400)."""
        # Débito: 1.210 en moneda de compañía, sin moneda secundaria.
        debit_line = self._receivable_line(1210.0, self.company_currency, 1210.0)
        # Crédito: 700 (compañía) / 0,50 EUR (pago manual en moneda secundaria
        # a la cotización del día: -700 × 1/1400 = -0,50).
        credit_line = self._receivable_line(-700.0, self.foreign_currency, -0.50)

        wizard = (
            self.env["account.reconcile.wizard"]
            .with_context(
                active_model="account.move.line",
                active_ids=(debit_line | credit_line).ids,
            )
            .create({})
        )

        # Con reconcile_on_company_currency el write-off debe estar en ARS.
        self.assertEqual(wizard.reco_currency_id, self.company_currency)
        # El importe debe ser la diferencia exacta en ARS, sin pérdida por redondeo
        # al pasar por moneda secundaria.
        self.assertAlmostEqual(wizard.amount, 510.0)
        self.assertAlmostEqual(wizard.amount_currency, 510.0)

    def _payable_line(self, account, date, balance, amount_currency):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": date,
                "journal_id": self.company_data["default_journal_misc"].id,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": account.id,
                            "partner_id": self.partner_a.id,
                            "balance": balance,
                            "currency_id": self.foreign_currency.id,
                            "amount_currency": amount_currency,
                        }
                    ),
                    Command.create(
                        {
                            "account_id": self.company_data["default_account_expense"].id,
                            "balance": -balance,
                            "currency_id": self.foreign_currency.id,
                            "amount_currency": -amount_currency,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        return move.line_ids.filtered(lambda l: l.account_id == account)

    def test_wizard_keeps_account_currency(self):
        """En una cuenta con moneda propia el write-off sale en esa moneda: una línea
        en moneda de compañía viola la restricción de moneda secundaria de la cuenta."""
        self.env["res.currency.rate"].create(
            {
                "name": "2016-02-01",
                "rate": 1 / 1450,
                "currency_id": self.foreign_currency.id,
                "company_id": self.company.id,
            }
        )
        account = self.env["account.account"].create(
            {
                "name": "Payable EUR",
                "code": "211099",
                "account_type": "liability_payable",
                "reconcile": True,
                "currency_id": self.foreign_currency.id,
            }
        )
        # -100 EUR a 1400 y +99,50 EUR a 1450: queda saldo en EUR y diferencia de cambio.
        credit_line = self._payable_line(account, self.date, -140000.0, -100.0)
        debit_line = self._payable_line(account, fields.Date.from_string("2016-02-01"), 144275.0, 99.50)

        wizard = (
            self.env["account.reconcile.wizard"]
            .with_context(
                active_model="account.move.line",
                active_ids=(credit_line | debit_line).ids,
            )
            .create({})
        )

        self.assertEqual(wizard.reco_currency_id, self.foreign_currency)
        self.assertAlmostEqual(abs(wizard.amount_currency), 0.50)

        wizard.write(
            {
                "account_id": self.company_data["default_account_expense"].id,
                "allow_partials": False,
            }
        )
        wizard.reconcile()

        self.assertTrue(credit_line.reconciled)
        self.assertTrue(debit_line.reconciled)
        write_off_line = (credit_line | debit_line).full_reconcile_id.reconciled_line_ids.filtered(
            lambda l: l.account_id == account and l not in credit_line | debit_line and l.amount_currency
        )
        self.assertEqual(write_off_line.currency_id, self.foreign_currency)
        self.assertAlmostEqual(abs(write_off_line.amount_currency), 0.50)
