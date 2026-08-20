# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account_reports.models.res_company import ResCompany as NativeCompany
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLegalEntityBranches(TransactionCase):
    """El override de ``_get_branches_with_same_vat`` responde con nuestro criterio.

    Ese método es el punto por donde Enterprise resuelve "qué branches son la misma
    entidad fiscal", y de él cuelgan los reportes fiscales que ignoran el selector de
    compañías, el hook de los botones de export
    (``enable_export_buttons_for_common_vat_in_branches``), si una declaración puede
    existir (``account_return._can_return_exist``) y el Libro Diario AR de upstream.
    Overrideándolo, todos esos consumidores pasan a usar el criterio sin tocarlos.

    El criterio en sí vive en ``account_ux``, con sus propios tests; acá se verifica
    solamente que el puente esté enchufado y que la diferencia con el comportamiento
    nativo sea la que buscamos.

    El puente vive en este módulo, y no en ``account_multicompany_ux``, para que ese
    módulo no dependa de Enterprise.
    """

    PARENT_VAT = "30111111118"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["res.company"].create({"name": "Casa Matriz", "vat": cls.PARENT_VAT})
        cls.same_vat = cls.env["res.company"].create(
            {"name": "Sucursal mismo CUIT", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT}
        )
        cls.no_vat = cls.env["res.company"].create(
            {"name": "Auxiliar sin CUIT", "parent_id": cls.parent.id, "vat": False}
        )

    def test_override_delegates_to_our_criterion(self):
        self.assertEqual(
            self.parent._get_branches_with_same_vat(),
            self.parent._get_legal_entity_companies(),
        )

    def test_branch_without_vat_is_left_out_of_the_group(self):
        """La diferencia concreta con el nativo, que la metería adentro por herencia."""
        self.assertNotIn(self.no_vat, self.parent._get_branches_with_same_vat())
        self.assertIn(self.same_vat, self.parent._get_branches_with_same_vat())

    def test_self_is_returned_first(self):
        """Contrato del método nativo: los llamadores lo usan para restaurar la cía activa."""
        self.assertEqual(self.same_vat._get_branches_with_same_vat()[0], self.same_vat)

    def test_accessible_only_is_honoured(self):
        """El parámetro del nativo tiene que seguir filtrando por ``env.companies``."""
        allowed = self.parent.with_context(allowed_company_ids=[self.parent.id])
        self.assertEqual(allowed._get_branches_with_same_vat(accessible_only=True), self.parent)

    # -------------------------------------------------------------------------
    # Pinning the traversal we replaced
    # -------------------------------------------------------------------------

    # Overriding the method wholesale means Enterprise's traversal —which companies of
    # the tree are even candidates, what ``accessible_only`` filters by, the self-first
    # contract— stops running for us. The criterion is meant to diverge; the traversal is
    # not. These tests compare both on data where the two criteria have to agree, so a
    # change Odoo makes to the traversal fails here instead of surfacing as a wrong VAT
    # book months later.

    OTHER_VAT = "30222222226"

    def _native_group(self, company, accessible_only=False):
        """The group Enterprise's own traversal returns, bypassing our override.

        Calls the unbound method of the class that defines it in ``account_reports``, the
        only way from here to run their algorithm over our data.
        """
        return NativeCompany._get_branches_with_same_vat(company, accessible_only=accessible_only)

    def _tree_where_every_company_declares_its_tax_id(self):
        """A tree with no empty Tax ID, so both criteria must give the same answer."""
        Company = self.env["res.company"]
        root = Company.create({"name": "Raíz declarada", "vat": self.PARENT_VAT})
        branch = Company.create({"name": "Sucursal declarada", "parent_id": root.id, "vat": self.PARENT_VAT})
        grandchild = Company.create({"name": "Nieta declarada", "parent_id": branch.id, "vat": self.PARENT_VAT})
        other = Company.create({"name": "Otra entidad", "parent_id": root.id, "vat": self.OTHER_VAT})
        other_branch = Company.create({"name": "Sucursal de la otra", "parent_id": other.id, "vat": self.OTHER_VAT})
        return root + branch + grandchild + other + other_branch

    def test_the_native_traversal_is_our_group_restricted_to_self_and_its_branches(self):
        """The invariant that has to hold on data where the criteria cannot disagree.

        Enterprise's traversal is directional: standing on a company it answers with that
        company and the branches **below** it. Ours answers with the whole legal entity,
        ancestors included. Everything else about the traversal —which companies are even
        candidates, the self-first contract— has to keep matching, so if Odoo changes it
        this fails here instead of showing up as a wrong VAT book months later.
        """
        for company in self._tree_where_every_company_declares_its_tax_id():
            ours = company._get_branches_with_same_vat()
            below = ours.filtered(lambda candidate: candidate == company or company in candidate.parent_ids)

            self.assertEqual(
                set(self._native_group(company).ids),
                set(below.ids),
                "the traversal diverged from Enterprise's for %s" % company.name,
            )
            self.assertEqual(ours[0], company, "self must come first, like the native contract")

    def test_accessible_only_keeps_the_same_invariant(self):
        tree = self._tree_where_every_company_declares_its_tax_id()
        allowed = tree[0] + tree[2]  # the root and its grandchild, skipping the branch between

        for company in allowed.with_context(allowed_company_ids=allowed.ids):
            ours = company._get_branches_with_same_vat(accessible_only=True)
            below = ours.filtered(lambda candidate: candidate == company or company in candidate.parent_ids)

            self.assertEqual(
                set(self._native_group(company, accessible_only=True).ids),
                set(below.ids),
                "accessible_only diverged from Enterprise's for %s" % company.name,
            )

    def test_our_group_also_reaches_the_ancestors_of_the_legal_entity(self):
        """The deliberate half of the divergence, and the one nothing else documents.

        A report or a return filed from a branch is the legal entity's, not the branch's
        own, so the group has to include the parent. Enterprise answers only downwards.
        """
        self.assertIn(self.parent, self.same_vat._get_branches_with_same_vat())
        self.assertNotIn(self.parent, self._native_group(self.same_vat))

    def test_the_head_of_the_entity_is_the_shallowest_of_the_group(self):
        """What ``_can_return_exist`` reads out of the group, so it deserves pinning.

        It sorts the group by depth and calls the shallowest one the main branch
        (``account_return.py:255-258``). Because our group reaches the ancestors, a branch
        sharing its parent's Tax ID is no longer its own main branch: the return belongs
        to the head of the entity and is filed there, which is the behaviour asked for.
        """
        group = self.same_vat._get_branches_with_same_vat()

        shallowest = min(group, key=lambda company: len(company.parent_path.split("/")))

        self.assertEqual(shallowest, self.parent)

    def test_the_only_divergence_left_is_the_company_without_a_tax_id(self):
        """Pins the divergence itself: the native traversal does take the empty Tax ID in.

        If this ever fails because both answers match, Enterprise changed its own rule —
        which is the day our override stops being needed.
        """
        self.assertIn(self.no_vat, self._native_group(self.parent))
        self.assertNotIn(self.no_vat, self.parent._get_branches_with_same_vat())
