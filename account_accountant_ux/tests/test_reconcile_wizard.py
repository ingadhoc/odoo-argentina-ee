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
