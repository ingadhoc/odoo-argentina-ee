from datetime import timedelta

from odoo import fields
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestBackwardPerception(TestArCommon):
    """A migrated IIBB perception is calculated with the equivalent tax of the partner."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls._create_journal("preprinted")
        states = cls.env["res.country.state"].search(
            [("country_id", "=", cls.env.ref("base.ar").id)], order="id", limit=2
        )
        cls.state, cls.other_state = states
        # the tax used when the document was posted
        cls.tax_perc_iibb.write({"amount_type": "percent", "amount": 3.0, "l10n_ar_state_id": cls.state.id})
        # the equivalent tax that the partner has in the new version
        cls.tax_partner = cls.tax_perc_iibb.copy({"name": "Perception of the partner", "active": True})

    def _get_amounts(self, move):
        base_lines, _tax_lines = move._get_rounded_base_and_tax_lines()
        return move._l10n_ar_get_amounts(base_lines=base_lines)

    def _create_posted_move(self, move_type="out_invoice", prices=(1000.0,), partner=None, **vals):
        move = self._create_invoice_ar(
            move_type=move_type,
            partner_id=(partner or self.res_partner_adhoc).id,
            journal_id=self.journal,
            **{"invoice_date": fields.Date.today(), **vals},
            invoice_line_ids=[
                self._prepare_invoice_line(
                    product_id=self.product_iva_21,
                    price_unit=price,
                    tax_ids=self.tax_21 + self.tax_perc_iibb + self.tax_internal,
                )
                for price in prices
            ],
        )
        draft = self._get_amounts(move)
        self.assertTrue(draft["iibb_perc_amount"])
        self._post(move)
        return move, draft

    def _migrate(self, tax, archive=True, backward=True):
        """Same state a migration leaves the old tax: archived and fixed in 0 (written in SQL, as Odoo forbids
        changing the computation of a tax with entries)."""
        tax.write({"is_backward_tax": backward})
        self.env.cr.execute(
            "UPDATE account_tax SET amount_type = 'fixed', amount = 0, active = %s WHERE id = %s",
            (not archive, tax.id),
        )
        self.env["account.tax"].invalidate_model()

    def _set_partner_tax(self, tax=None, **vals):
        return self.env["l10n_ar.partner.tax"].create(
            {
                "partner_id": self.res_partner_adhoc.id,
                "tax_id": (tax or self.tax_partner).id,
                "company_id": self.env.company.id,
                **vals,
            }
        )

    def test_invoice_uses_the_tax_of_the_partner(self):
        move, draft = self._create_posted_move()
        self._migrate(self.tax_perc_iibb)
        self._set_partner_tax()
        self.assertEqual(self._get_amounts(move), draft)

    def test_credit_note_uses_the_tax_of_the_partner(self):
        move, draft = self._create_posted_move("out_refund")
        self._migrate(self.tax_perc_iibb)
        self._set_partner_tax()
        self.assertEqual(self._get_amounts(move), draft)

    def test_without_tax_in_the_partner_keeps_the_tax(self):
        move, _draft = self._create_posted_move()
        self._migrate(self.tax_perc_iibb)
        self.assertEqual(self._get_amounts(move)["iibb_perc_amount"], 0.0)

    def test_tax_of_the_partner_out_of_dates_is_not_used(self):
        move, _draft = self._create_posted_move()
        self._migrate(self.tax_perc_iibb)
        self._set_partner_tax(from_date=fields.Date.today() + timedelta(days=1))
        self.assertEqual(self._get_amounts(move)["iibb_perc_amount"], 0.0)

    def test_tax_of_the_partner_of_other_jurisdiction_is_not_used(self):
        move, _draft = self._create_posted_move()
        self._migrate(self.tax_perc_iibb)
        self.tax_partner.l10n_ar_state_id = self.other_state
        self._set_partner_tax()
        self.assertEqual(self._get_amounts(move)["iibb_perc_amount"], 0.0)

    def test_tax_not_archived_is_not_replaced(self):
        """An active backward tax was created in the new version, so it is not a migrated one."""
        move, _draft = self._create_posted_move()
        self._migrate(self.tax_perc_iibb, archive=False)
        self._set_partner_tax()
        self.assertEqual(self._get_amounts(move)["iibb_perc_amount"], 0.0)

    def test_tax_not_backward_is_not_replaced(self):
        move, _draft = self._create_posted_move()
        self._migrate(self.tax_perc_iibb, backward=False)
        self._set_partner_tax()
        self.assertEqual(self._get_amounts(move)["iibb_perc_amount"], 0.0)

    def test_other_backward_taxes_are_not_replaced(self):
        """Only the IIBB perceptions are replaced."""
        move, draft = self._create_posted_move()
        self._migrate(self.tax_internal)
        self._set_partner_tax()
        after = self._get_amounts(move)
        self.assertTrue(draft["intern_tax_amount"])
        self.assertEqual(after["intern_tax_amount"], 0.0)
        self.assertEqual(after["iibb_perc_amount"], draft["iibb_perc_amount"])

    def test_tax_without_jurisdiction_is_not_replaced(self):
        """A partner tax of an unrelated tax without jurisdiction must not match."""
        move, _draft = self._create_posted_move()
        self._migrate(self.tax_perc_iibb)
        self.env.cr.execute(
            "UPDATE account_tax SET l10n_ar_state_id = NULL WHERE id IN %s",
            (tuple((self.tax_perc_iibb + self.tax_partner).ids),),
        )
        self.env["account.tax"].invalidate_model()
        self._set_partner_tax()
        self.assertEqual(self._get_amounts(move)["iibb_perc_amount"], 0.0)

    def test_other_calculations_of_the_document_are_not_changed(self):
        """The replacement only applies to the amounts of the document, not to its tax totals."""
        move, _draft = self._create_posted_move()
        self._migrate(self.tax_perc_iibb)
        self._set_partner_tax()
        move.invalidate_recordset(["tax_totals"])
        totals = move.tax_totals
        self.assertTrue(self._get_amounts(move)["iibb_perc_amount"])
        move.invalidate_recordset(["tax_totals"])
        self.assertEqual(move.tax_totals, totals)

    def test_rounding_with_several_lines(self):
        move, draft = self._create_posted_move(prices=(33.33, 66.67, 12.35, 7.77))
        self._migrate(self.tax_perc_iibb)
        self._set_partner_tax()
        self.assertEqual(self._get_amounts(move), draft)

    def test_invoice_addressed_to_a_contact_uses_the_tax_of_the_commercial_partner(self):
        contact = self.env["res.partner"].create(
            {"name": "Invoice contact", "parent_id": self.res_partner_adhoc.id, "type": "invoice"}
        )
        move, draft = self._create_posted_move(partner=contact)
        self.assertEqual(move.commercial_partner_id, self.res_partner_adhoc)
        self._migrate(self.tax_perc_iibb)
        self._set_partner_tax()
        self.assertEqual(self._get_amounts(move), draft)

    def test_base_lines_received_are_used(self):
        """The amounts are calculated with the base lines received, replacing only the migrated taxes."""
        move, _draft = self._create_posted_move(prices=(1000.0, 500.0))
        self._migrate(self.tax_perc_iibb)
        self._set_partner_tax()
        base_lines, _tax_lines = move._get_rounded_base_and_tax_lines()
        amounts = move._l10n_ar_get_amounts(base_lines=base_lines[:1])
        self.assertEqual(amounts["iibb_perc_amount"], 30.0)
        self.assertEqual(amounts["vat_taxable_amount"], 1000.0)
        self.assertEqual(move._l10n_ar_get_amounts(base_lines=base_lines)["iibb_perc_amount"], 45.0)

    def test_draft_keeps_the_taxes_of_the_document(self):
        """A draft is calculated with its own taxes: the totals of the document do not include the replacement."""
        move = self._create_invoice_ar(
            partner_id=self.res_partner_adhoc.id,
            journal_id=self.journal,
            invoice_date=fields.Date.today(),
            invoice_line_ids=[
                self._prepare_invoice_line(
                    product_id=self.product_iva_21, price_unit=1000.0, tax_ids=self.tax_21 + self.tax_perc_iibb
                )
            ],
        )
        self._migrate(self.tax_perc_iibb)
        self._set_partner_tax()
        self.assertEqual(self._get_amounts(move)["iibb_perc_amount"], 0.0)
