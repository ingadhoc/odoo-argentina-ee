##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common


class TestSircipConstraint(common.TransactionCase):
    """Tests para el override del constraint de unicidad en l10n_ar.partner.tax."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Buscar impuestos SIRCIP de la compañía demo
        cls.sircip_group = cls.env["account.tax.group"].search(
            [
                ("name", "=", "SIRCIP"),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )
        cls.sircip_taxes = cls.env["account.tax"].search(
            [
                ("tax_group_id", "=", cls.sircip_group.id),
                ("company_id", "=", cls.env.company.id),
                ("type_tax_use", "=", "sale"),
            ]
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Partner Test SIRCIP Constraint",
                "vat": "30683021209",  # CUIT válido del padron demo
                "l10n_latam_identification_type_id": cls.env.ref("l10n_ar.it_cuit").id,
            }
        )

    def setUp(self):
        super().setUp()
        if not self.sircip_group or not self.sircip_taxes:
            self.skipTest("No hay datos SIRCIP en la compañía. Instalar el módulo primero.")

    def test_multiple_sircip_perceptions_same_period_allowed(self):
        """Se permite crear múltiples registros del grupo SIRCIP para el mismo
        partner y período (necesario para un contacto con entregas en varias provincias)."""
        from_date = fields.Date.from_string("2026-02-01")
        to_date = fields.Date.from_string("2026-02-28")
        # Usar dos impuestos SIRCIP distintos (ambos del mismo tax_group)
        taxes = self.sircip_taxes[:2]
        if len(taxes) < 2:
            self.skipTest("Se necesitan al menos 2 impuestos SIRCIP para este test")

        # Crear primer registro — no debe lanzar error
        rec1 = self.env["l10n_ar.partner.tax"].create(
            {
                "partner_id": self.partner.id,
                "tax_id": taxes[0].id,
                "from_date": from_date,
                "to_date": to_date,
                "ref": "SIRCIP | crc:25 | campo7:5214252222222225522522550",
            }
        )
        # Crear segundo registro con el mismo grupo/período — no debe lanzar error
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
        """El constraint original sigue bloqueando duplicados para impuestos no-SIRCIP."""
        # Buscar un impuesto no-SIRCIP con tax_group definido
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
            self.skipTest("No hay impuestos no-SIRCIP con tax_group para testear")

        from_date = fields.Date.from_string("2026-03-01")
        to_date = fields.Date.from_string("2026-03-31")
        partner2 = self.env["res.partner"].create(
            {
                "name": "Partner Non-SIRCIP Test",
                "vat": "30683013184",  # CUIT válido del padron demo
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
        # El segundo registro con el mismo grupo/período debe fallar
        with self.assertRaises(ValidationError):
            self.env["l10n_ar.partner.tax"].create(
                {
                    "partner_id": partner2.id,
                    "tax_id": non_sircip_tax.id,
                    "from_date": from_date,
                    "to_date": to_date,
                }
            )
