# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestBlockIntercompanyReconciliation(AccountTestInvoicingCommon):
    """El bloqueo se mira en la raíz del árbol, también cuando la padre no está entre los apuntes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root_company = cls.company_data["company"]
        cls.root_company.write(
            {
                "child_ids": [
                    Command.create({"name": "Branch A"}),
                    Command.create({"name": "Branch B"}),
                ],
            }
        )
        cls.cr.precommit.run()  # load the CoA
        cls.branch_a, cls.branch_b = cls.root_company.child_ids
        invoice = cls.init_invoice("out_invoice", amounts=[100.0], company=cls.branch_a, post=True)
        refund = cls.init_invoice("out_refund", amounts=[100.0], company=cls.branch_b, post=True)
        cls.lines = (invoice + refund).line_ids.filtered(lambda l: l.display_type == "payment_term")

    def _wizard(self):
        return (
            self.env["account.reconcile.wizard"]
            .with_context(
                active_model="account.move.line",
                active_ids=self.lines.ids,
                allowed_company_ids=(self.root_company + self.branch_a + self.branch_b).ids,
            )
            .create({})
        )

    def test_sibling_branches_are_blocked_by_the_root(self):
        self.root_company.block_intercompany_conciliation = "all"
        with self.assertRaises(UserError):
            self._wizard().reconcile()

    def test_sibling_branches_reconcile_without_the_block(self):
        self._wizard().reconcile()
        self.assertTrue(all(self.lines.mapped("reconciled")))

    def test_blocked_between_legal_entities(self):
        """Sin CUIT cada sucursal es su propia entidad fiscal y se bloquea; con el mismo CUIT, no."""
        self.root_company.block_intercompany_conciliation = "other_legal_entity"
        with self.assertRaises(UserError):
            self._wizard().reconcile()

        companies = self.root_company + self.branch_a + self.branch_b
        companies.country_id = False
        companies.vat = "30111111118"
        self._wizard().reconcile()
        self.assertTrue(all(self.lines.mapped("reconciled")))
