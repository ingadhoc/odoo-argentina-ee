# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLegalEntityFiscalYear(TransactionCase):
    """The explicit fiscal year belongs to the legal entity, on its head.

    ``account_ux`` moves ``fiscalyear_last_day`` / ``fiscalyear_last_month`` from the
    root tier to the legal entity tier. This is the half of that change which needs
    Enterprise: the ``account.fiscal.year`` model, whose constraint banned any explicit
    fiscal year outside the root company, and ``compute_fiscalyear_dates``, which is the
    only consumer that reads those records.

    Both halves have to move together. The explicit record wins over the fields, so a
    branch that heads its own legal entity would be able to set the fields and still be
    unable to declare an irregular year — and a branch inside an entity would never find
    the record its own head declared.
    """

    PARENT_VAT = "30111111118"
    OTHER_VAT = "30222222227"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        cls.parent = Company.create(
            {
                "name": "Casa Matriz",
                "vat": cls.PARENT_VAT,
                "fiscalyear_last_day": 30,
                "fiscalyear_last_month": "6",
            }
        )
        cls.same_entity = Company.create(
            {"name": "Sucursal mismo CUIT", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT}
        )
        cls.other_entity = Company.create(
            {"name": "Otra razón social", "parent_id": cls.parent.id, "vat": cls.OTHER_VAT}
        )
        cls.FiscalYear = cls.env["account.fiscal.year"]

    def _create_fiscal_year(self, company, date_from, date_to):
        return self.FiscalYear.create(
            {
                "name": "Ejercicio %s" % company.name,
                "company_id": company.id,
                "date_from": date_from,
                "date_to": date_to,
            }
        )

    # ------------------------------------------------------------------
    # Who may declare an explicit fiscal year
    # ------------------------------------------------------------------

    def test_the_root_company_may_declare_one(self):
        """Unchanged: it is the only case core allowed."""
        fiscal_year = self._create_fiscal_year(self.parent, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(fiscal_year.company_id, self.parent)

    def test_a_branch_that_heads_its_own_entity_may_declare_one(self):
        """The case core rejected with "You cannot have a fiscal year on a child company"."""
        fiscal_year = self._create_fiscal_year(self.other_entity, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(fiscal_year.company_id, self.other_entity)

    def test_a_branch_inside_an_entity_may_not_declare_one(self):
        """The ban stays for the rest of the entity: the year is declared once, on the head."""
        with self.assertRaises(ValidationError):
            self._create_fiscal_year(self.same_entity, date(2026, 1, 1), date(2026, 12, 31))

    def test_overlapping_fiscal_years_are_still_rejected(self):
        """The rest of the constraint is a verbatim copy and has to keep working."""
        self._create_fiscal_year(self.parent, date(2026, 1, 1), date(2026, 12, 31))
        with self.assertRaises(ValidationError):
            self._create_fiscal_year(self.parent, date(2026, 6, 1), date(2027, 5, 31))

    def test_the_ending_date_is_still_checked(self):
        with self.assertRaises(ValidationError):
            self._create_fiscal_year(self.parent, date(2026, 12, 31), date(2026, 1, 1))

    def test_the_default_company_is_the_head_of_the_active_entity(self):
        """Standing on a branch of an entity, the new fiscal year is offered for its head."""
        default = self.FiscalYear.with_company(self.same_entity).default_get(["company_id"])
        self.assertEqual(default["company_id"], self.parent.id)

    # ------------------------------------------------------------------
    # Who reads it
    # ------------------------------------------------------------------

    def test_a_branch_of_the_entity_reads_the_fiscal_year_of_its_head(self):
        """Without the override it would answer 2025-07-01 / 2026-06-30, from the fields."""
        self._create_fiscal_year(self.parent, date(2026, 1, 1), date(2026, 12, 31))
        dates = self.same_entity.compute_fiscalyear_dates(date(2026, 3, 1))
        self.assertEqual(dates["date_from"], date(2026, 1, 1))
        self.assertEqual(dates["date_to"], date(2026, 12, 31))
        self.assertEqual(dates, self.parent.compute_fiscalyear_dates(date(2026, 3, 1)))

    def test_a_company_of_another_entity_reads_its_own(self):
        self._create_fiscal_year(self.parent, date(2026, 1, 1), date(2026, 12, 31))
        self.other_entity.write({"fiscalyear_last_day": 31, "fiscalyear_last_month": "3"})
        dates = self.other_entity.compute_fiscalyear_dates(date(2026, 6, 1))
        self.assertEqual(dates["date_from"], date(2026, 4, 1))
        self.assertEqual(dates["date_to"], date(2027, 3, 31))

    def test_without_explicit_fiscal_years_the_fields_still_answer(self):
        dates = self.same_entity.compute_fiscalyear_dates(date(2026, 3, 1))
        self.assertEqual(dates["date_from"], date(2025, 7, 1))
        self.assertEqual(dates["date_to"], date(2026, 6, 30))
