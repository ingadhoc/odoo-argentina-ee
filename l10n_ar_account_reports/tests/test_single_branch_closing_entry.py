##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from contextlib import ExitStack
from unittest.mock import patch

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSingleBranchClosingEntry(AccountTestInvoicingCommon):
    """Valida el flag ``l10n_ar_single_branch_closing_entry`` del tipo de retorno.

    Aislamos la lógica de consolidación de ``_generate_tax_closing_entries``:
    parcheamos los helpers pesados (cómputo de líneas por compañía, validación de
    grupos de impuesto, diario de cierre y posteo) para no depender del plan de
    cuentas AR ni de facturas reales, y verificamos únicamente cuántos asientos se
    crean y en qué compañía.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.parent_company = cls.company_data["company"]
        # Sucursal / branch directa de la compañía padre (comparte plan de cuentas).
        cls.branch = cls.env["res.company"].create(
            {
                "name": "Sucursal Test",
                "parent_id": cls.parent_company.id,
                "currency_id": cls.parent_company.currency_id.id,
            }
        )
        # Sub-sucursal: branch de la branch (segundo nivel de anidamiento).
        cls.sub_branch = cls.env["res.company"].create(
            {
                "name": "Sub-sucursal Test",
                "parent_id": cls.branch.id,
                "currency_id": cls.parent_company.currency_id.id,
            }
        )
        cls.all_companies = cls.parent_company + cls.branch + cls.sub_branch

        # Compañía independiente (sin parent_id): simula una unidad de impuestos (tax unit) con
        # compañías NO relacionadas. No debe disparar la consolidación de sucursales.
        cls.unrelated_company_data = cls.setup_other_company()
        cls.unrelated_company = cls.unrelated_company_data["company"]

        # Reporte de impuestos mínimo para poder crear el tipo de retorno.
        cls.report = cls.env["account.report"].create(
            {
                "name": "Test branch closing report",
                "country_id": cls.parent_company.account_fiscal_country_id.id,
                "root_report_id": cls.env.ref("account.generic_tax_report").id,
                "column_ids": [Command.create({"name": "Balance", "sequence": 1, "expression_label": "balance"})],
            }
        )
        cls.return_type = cls.env["account.return.type"].create(
            {
                "name": "Branch Closing Return",
                "report_id": cls.report.id,
            }
        )

        # Un diario de cierre por compañía (el move debe tener el diario de su propia compañía).
        cls.journal_by_company = {}
        for company in cls.all_companies + cls.unrelated_company:
            cls.journal_by_company[company.id] = cls.env["account.journal"].create(
                {
                    "name": f"Tax Closing {company.name}",
                    "code": f"TC{company.id}",
                    "type": "general",
                    "company_id": company.id,
                }
            )

        # Cuenta válida por compañía: el padre (raíz del árbol) la comparte con su sucursal;
        # la compañía no relacionada usa la suya propia (otro plan de cuentas).
        cls.account_by_company = {
            cls.parent_company.id: cls.company_data["default_account_expense"],
            cls.branch.id: cls.company_data["default_account_expense"],
            cls.sub_branch.id: cls.company_data["default_account_expense"],
            cls.unrelated_company.id: cls.unrelated_company_data["default_account_expense"],
        }

    # ------------------------------------------------------------------
    # Helpers de parcheo
    # ------------------------------------------------------------------
    def _patched_env(self, company_ids=None, with_counterpart=True):
        """Devuelve la lista de patches que aíslan la lógica bajo test.

        :param company_ids: conjunto de compañías que abarca el return (default: padre + sucursal).
        :param with_counterpart: si False, el helper de contrapartida no agrega línea (útil para el
            caso multi-compañía no relacionado, donde cada asiento vive en su propia compañía y no
            hay una cuenta común válida para la contrapartida).
        """
        test = self
        companies = company_ids if company_ids is not None else self.all_companies
        return_model = self.registry["account.return"]
        company_model = self.registry["res.company"]
        move_model = self.registry["account.move"]

        def fake_get_company_ids(self, main_company, tax_unit, report):
            return companies

        def fake_ensure_tax_group(self):
            return True

        def fake_compute_tax_closing_entry(self, company, options):
            # Una línea por compañía, identificable por su nombre y con una cuenta válida en ella.
            account = test.account_by_company[company.id]
            lines = [
                Command.create(
                    {
                        "name": f"tax {company.name}",
                        "debit": 100.0,
                        "credit": 0.0,
                        "account_id": account.id,
                    }
                )
            ]
            if not with_counterpart:
                # Sin contrapartida común (caso multi-compañía no relacionado): balanceamos el
                # asiento dentro de su propia compañía para que el create nativo no lo rechace.
                lines.append(
                    Command.create(
                        {
                            "name": f"tax counterpart {company.name}",
                            "debit": 0.0,
                            "credit": 100.0,
                            "account_id": account.id,
                        }
                    )
                )
                return lines, {("k",): 0.0}
            return lines, {("k",): -100.0}

        def fake_add_tax_group_closing_items(self, tax_group_subtotal):
            if not with_counterpart:
                return []
            total = sum(tax_group_subtotal.values())
            return [
                Command.create(
                    {
                        "name": "counterpart",
                        "debit": 0.0,
                        "credit": abs(total),
                        "account_id": test.account_by_company[self.company_id.id].id,
                    }
                )
            ]

        def fake_get_tax_closing_journal(self):
            return test.journal_by_company[self.id]

        def fake_action_post(self):
            # No posteamos: el test solo verifica la creación de los asientos.
            return True

        return [
            patch.object(return_model, "_get_company_ids", fake_get_company_ids),
            patch.object(return_model, "_ensure_tax_group_configuration_for_tax_closing", fake_ensure_tax_group),
            patch.object(return_model, "_compute_tax_closing_entry", fake_compute_tax_closing_entry),
            patch.object(return_model, "_add_tax_group_closing_items", fake_add_tax_group_closing_items),
            patch.object(company_model, "_get_tax_closing_journal", fake_get_tax_closing_journal),
            patch.object(move_model, "action_post", fake_action_post),
        ]

    def _create_return(self, expected_companies=None):
        expected_companies = expected_companies if expected_companies is not None else self.all_companies
        tax_return = self.env["account.return"].create(
            {
                "name": "Return test",
                "type_id": self.return_type.id,
                "company_id": self.parent_company.id,
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
            }
        )
        # company_ids es computado/stored; forzamos el recálculo con el patch activo.
        tax_return.invalidate_recordset(["company_ids"])
        self.assertEqual(
            tax_return.company_ids,
            expected_companies,
            "El setup debe dejar el return abarcando las compañías esperadas.",
        )
        return tax_return

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_single_consolidated_entry_when_flag_enabled(self):
        """Con el flag activo y sucursales —incluyendo sub-sucursales (jerarquía multinivel
        padre → sucursal → sub-sucursal)— se crea un único asiento consolidado en la padre."""
        self.return_type.l10n_ar_single_branch_closing_entry = True

        with ExitStack() as stack:
            for patcher in self._patched_env():
                stack.enter_context(patcher)
            tax_return = self._create_return()
            tax_return._generate_tax_closing_entries({})

        self.assertEqual(
            len(tax_return.closing_move_ids),
            1,
            "Con consolidación debe generarse un solo asiento de liquidación.",
        )
        self.assertEqual(
            tax_return.closing_move_ids.company_id,
            self.parent_company,
            "El asiento consolidado debe quedar en la compañía padre.",
        )
        # 1 línea por compañía (padre + sucursal + sub-sucursal = 3) + 1 contrapartida = 4.
        self.assertEqual(
            len(tax_return.closing_move_ids.line_ids),
            4,
            "El asiento consolidado debe contener las líneas de todas las compañías del árbol.",
        )

    def test_one_entry_per_company_when_flag_disabled(self):
        """Sin el flag, se mantiene el comportamiento nativo: un asiento por compañía."""
        self.return_type.l10n_ar_single_branch_closing_entry = False

        with ExitStack() as stack:
            for patcher in self._patched_env():
                stack.enter_context(patcher)
            tax_return = self._create_return()
            tax_return._generate_tax_closing_entries({})

        self.assertEqual(
            len(tax_return.closing_move_ids),
            3,
            "Sin consolidación debe generarse un asiento por compañía (padre + sucursal + sub-sucursal).",
        )
        self.assertEqual(
            tax_return.closing_move_ids.company_id,
            self.all_companies,
            "Debe haber un asiento por cada compañía del return.",
        )

    def test_no_consolidation_for_unrelated_multicompany(self):
        """Con el flag activo pero compañías NO relacionadas (sin relación parent_id), NO se
        consolida: se delega al comportamiento nativo (un asiento por compañía).

        Cubre el caso que motivó la observación de review: una unidad de impuestos (tax unit) con
        compañías independientes no debe tratarse como un grupo de sucursales solo porque
        ``len(company_ids) > 1``.
        """
        self.return_type.l10n_ar_single_branch_closing_entry = True
        unrelated_set = self.parent_company + self.unrelated_company

        with ExitStack() as stack:
            for patcher in self._patched_env(company_ids=unrelated_set, with_counterpart=False):
                stack.enter_context(patcher)
            tax_return = self._create_return(expected_companies=unrelated_set)
            tax_return._generate_tax_closing_entries({})

        self.assertEqual(
            len(tax_return.closing_move_ids),
            2,
            "Compañías no relacionadas no se consolidan: un asiento por compañía.",
        )
        self.assertEqual(
            tax_return.closing_move_ids.company_id,
            unrelated_set,
            "Debe haber un asiento por cada compañía no relacionada del return.",
        )
