# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.exceptions import ValidationError
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestSettlementJournalEntryBranches(common.TransactionCase):
    """El asiento de liquidación tenía dos gates de compañía contradictorios: el gate
    nativo (branch_allowed ausente) exige toda la jerarquía de branches seleccionada,
    el propio exigía exactamente 1 compañía. El criterio correcto es el grupo de
    compañías que comparten CUIT (res.company._get_branches_with_same_vat)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent_company = cls.env.company
        cls.same_vat_branch = cls.env["res.company"].create(
            {"name": "Sucursal mismo CUIT", "parent_id": cls.parent_company.id}
        )
        cls.diff_vat_branch = cls.env["res.company"].create(
            {
                "name": "Empresa relacionada CUIT distinto",
                "parent_id": cls.parent_company.id,
                "vat": "30-22222222-3",
            }
        )
        cls.report = cls.env["account.report"].create(
            {
                "name": "Test Settlement Report",
                "allow_settlement": True,
                "settlement_title": "Liquidar Test",
            }
        )
        cls.parent_journal = cls.env["account.journal"].create(
            {"name": "General Padre", "type": "general", "company_id": cls.parent_company.id}
        )
        cls.same_vat_journal = cls.env["account.journal"].create(
            {"name": "General Sucursal mismo CUIT", "type": "general", "company_id": cls.same_vat_branch.id}
        )
        cls.diff_vat_journal = cls.env["account.journal"].create(
            {"name": "General Empresa CUIT distinto", "type": "general", "company_id": cls.diff_vat_branch.id}
        )

    def _options(self, journals):
        return {"journals": [{"id": journal.id, "model": "account.journal"} for journal in journals]}

    def test_settlement_allows_same_vat_branches(self):
        """Diarios de padre + hija con mismo CUIT: debe habilitar, usando la padre
        (raíz del grupo) como compañía del asiento."""
        options = self._options(self.parent_journal + self.same_vat_journal)
        action = self.report.action_closure_journal_entry(options)
        self.assertEqual(action["res_model"], "account.tax.settlement.wizard")
        self.assertEqual(action["context"]["default_company_id"], self.parent_company.id)

    def test_settlement_blocks_different_vat_branches(self):
        """Diarios de padre + hija con CUIT distinto: debe bloquear, no mezclar
        entidades fiscales distintas en un mismo asiento."""
        options = self._options(self.parent_journal + self.diff_vat_journal)
        with self.assertRaises(ValidationError):
            self.report.action_closure_journal_entry(options)

    def test_settlement_still_works_single_company(self):
        """El caso sin branches (una sola compañía) sigue funcionando igual que antes."""
        options = self._options(self.parent_journal)
        action = self.report.action_closure_journal_entry(options)
        self.assertEqual(action["context"]["default_company_id"], self.parent_company.id)

    def test_settlement_enables_common_vat_option_on_buttons(self):
        """_init_options_buttons debe levantar el gate nativo de branches para el
        grupo de mismo CUIT, no solo agregar el botón."""
        options = {}
        self.report._init_options_buttons(options, {})
        self.assertTrue(options.get("enable_export_buttons_for_common_vat_in_branches"))
