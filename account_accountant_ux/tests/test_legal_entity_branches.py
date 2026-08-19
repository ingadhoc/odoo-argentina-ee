# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
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
