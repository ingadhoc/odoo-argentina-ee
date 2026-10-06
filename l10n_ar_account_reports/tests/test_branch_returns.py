##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestLegalEntityBranchReturns(AccountTestInvoicingCommon):
    """Una sucursal argentina con otro CUIT tiene sus propias declaraciones.

    Enterprise solo crea declaraciones para una sucursal con otro CUIT si tiene fecha de
    apertura propia, y las sucursales nacen sin ella. Además, cambiar el CUIT no refresca
    las declaraciones hasta el cron diario.
    """

    PARENT_VAT = "30111111118"
    OTHER_VAT = "30716666669"
    OPENING_DATE = "2026-01-01"

    @classmethod
    @AccountTestInvoicingCommon.setup_country("ar")
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.company_data["company"]
        cls.parent.write({"vat": cls.PARENT_VAT, "account_opening_date": cls.OPENING_DATE})

    def _returns_of(self, company):
        return self.env["account.return"].sudo().search_count([("company_id", "=", company.id)])

    def test_branch_with_other_vat_gets_opening_date_and_returns(self):
        branch = self._create_company(name="Servicios SRL", parent_id=self.parent.id, vat=self.OTHER_VAT)

        self.assertEqual(str(branch.account_opening_date), self.OPENING_DATE)
        self.assertTrue(self._returns_of(branch))

    def test_branch_with_same_vat_keeps_no_opening_date(self):
        """Sus declaraciones son las de la padre: no se le inventa una fecha."""
        branch = self._create_company(name="Rosario", parent_id=self.parent.id, vat=self.PARENT_VAT)

        self.assertFalse(branch.account_opening_date)
        self.assertFalse(self._returns_of(branch))

    def test_branch_without_vat_keeps_no_opening_date(self):
        """Una auxiliar sin CUIT no está sujeta a impuestos."""
        branch = self._create_company(name="Auxiliar", parent_id=self.parent.id, vat=False)

        self.assertFalse(branch.account_opening_date)

    def test_vat_change_refreshes_returns(self):
        """La sucursal ya tenía fecha de apertura: el cambio de CUIT alcanza para refrescar."""
        branch = self._create_company(
            name="Servicios SRL",
            parent_id=self.parent.id,
            vat=self.PARENT_VAT,
            account_opening_date=self.OPENING_DATE,
        )
        self.assertFalse(self._returns_of(branch))

        branch.vat = self.OTHER_VAT

        self.assertTrue(self._returns_of(branch))

    def test_branch_of_another_country_is_left_as_is(self):
        """Fuera de Argentina se mantiene el comportamiento nativo."""
        us = self.env.ref("base.us")
        us_vals = {"country_id": us.id, "currency_id": us.currency_id.id}
        parent = self.env["res.company"].create(
            {**us_vals, "name": "US Parent", "vat": "123456789", "account_opening_date": self.OPENING_DATE}
        )
        branch = self.env["res.company"].create(
            {**us_vals, "name": "US Branch", "parent_id": parent.id, "vat": "987654321"}
        )
        self.assertNotEqual(branch.account_fiscal_country_id.code, "AR")

        self.assertFalse(branch.account_opening_date)

    def test_vat_help_does_not_suggest_slash(self):
        self.assertNotIn("'/'", self.env["res.company"]._fields["vat"].help)
