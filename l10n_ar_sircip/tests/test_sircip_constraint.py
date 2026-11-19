##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common


class TestSircipConstraint(common.TransactionCase):
    """Override of the l10n_ar.partner.tax overlap constraint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # SIRCIP data only exists for AR-chart companies: switch to company_ri.
        company_ri = cls.env.ref("base.company_ri")
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[company_ri.id]))
        cls.sircip_group = cls.env["account.tax.group"].search(
            [
                ("name", "=", "SIRCIP"),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )
        cls.sircip_taxes = (
            cls.env["account.tax"]
            .with_context(active_test=False)
            .search(
                [
                    ("tax_group_id", "=", cls.sircip_group.id),
                    ("company_id", "=", cls.env.company.id),
                    ("type_tax_use", "=", "sale"),
                ]
            )
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Partner Test SIRCIP Constraint",
                "vat": "30888888884",
                "l10n_latam_identification_type_id": cls.env.ref("l10n_ar.it_cuit").id,
            }
        )

    def setUp(self):
        super().setUp()
        if not self.sircip_group or not self.sircip_taxes:
            self.skipTest("No SIRCIP data in the company: install the module first.")

    def test_multiple_sircip_perceptions_same_period_allowed(self):
        """Several SIRCIP records for the same partner and period are allowed."""
        from_date = fields.Date.today().replace(day=1)
        to_date = fields.Date.end_of(from_date, "month")
        taxes = self.sircip_taxes[:2]
        if len(taxes) < 2:
            self.skipTest("At least 2 SIRCIP taxes are needed")

        rec1 = self.env["l10n_ar.partner.tax"].create(
            {
                "partner_id": self.partner.id,
                "tax_id": taxes[0].id,
                "from_date": from_date,
                "to_date": to_date,
                "ref": "SIRCIP | crc:25 | campo7:5214252222222225522522550",
            }
        )
        rec2 = self.env["l10n_ar.partner.tax"].create(
            {
                "partner_id": self.partner.id,
                "tax_id": taxes[1].id,
                "from_date": from_date,
                "to_date": to_date,
                "ref": "SIRCIP | crc:84 | campo7:5224252222222225522512550",
            }
        )
        self.assertTrue(rec1.id)
        self.assertTrue(rec2.id)

    def test_non_sircip_duplicate_still_blocked(self):
        """The original constraint still blocks duplicates of non-SIRCIP taxes."""
        non_sircip_tax = self.env["account.tax"].search(
            [
                ("tax_group_id.name", "!=", "SIRCIP"),
                ("company_id", "=", self.env.company.id),
                ("type_tax_use", "=", "sale"),
                ("tax_group_id", "!=", False),
            ],
            limit=1,
        )
        if not non_sircip_tax:
            self.skipTest("No non-SIRCIP tax with a tax group to test")

        from_date = fields.Date.today().replace(day=1)
        to_date = fields.Date.end_of(from_date, "month")
        partner2 = self.env["res.partner"].create(
            {
                "name": "Partner Non-SIRCIP Test",
                "vat": "33222222228",
                "l10n_latam_identification_type_id": self.env.ref("l10n_ar.it_cuit").id,
            }
        )
        self.env["l10n_ar.partner.tax"].create(
            {
                "partner_id": partner2.id,
                "tax_id": non_sircip_tax.id,
                "from_date": from_date,
                "to_date": to_date,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["l10n_ar.partner.tax"].create(
                {
                    "partner_id": partner2.id,
                    "tax_id": non_sircip_tax.id,
                    "from_date": from_date,
                    "to_date": to_date,
                }
            )
