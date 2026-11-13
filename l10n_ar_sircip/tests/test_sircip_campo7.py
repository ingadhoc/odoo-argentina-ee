##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.addons.l10n_ar_sircip.models.account_fiscal_position_l10n_ar_tax import (
    SIRCIP_CAMPO7_POSITION,
)
from odoo.tests import common


class TestSircipCampo7(common.TransactionCase):
    """Padron field 7: jurisdiction position map and digit lookup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # SIRCIP data only exists for AR-chart companies: switch to company_ri.
        company_ri = cls.env.ref("base.company_ri")
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[company_ri.id]))

    def _get_fiscal_pos_line(self):
        """SIRCIP fiscal position line to call the methods on."""
        fiscal_pos = self.env["account.fiscal.position"].create(
            {
                "name": "Test SIRCIP",
                "company_id": self.env.company.id,
            }
        )
        # SIRCIP "no inscripto" tax
        sircip_tax = self.env["account.tax"].search(
            [
                ("l10n_ar_sircip_record_type", "=", "4"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if not sircip_tax:
            self.skipTest("No SIRCIP taxes in the demo company")
        return self.env["account.fiscal.position.l10n_ar_tax"].create(
            {
                "fiscal_position_id": fiscal_pos.id,
                "default_tax_id": sircip_tax.id,
                "tax_type": "perception",
                "webservice": "padron",
            }
        )

    def test_position_formula(self):
        """Every index equals 924 - jurisdiction_code."""
        for jcode_str, idx in SIRCIP_CAMPO7_POSITION.items():
            jcode = int(jcode_str)
            expected = 924 - jcode
            self.assertEqual(
                idx,
                expected,
                "JC=%s should be at index %s, not %s" % (jcode_str, expected, idx),
            )

    def test_caba_position(self):
        """CABA (901) is at index 23."""
        self.assertEqual(SIRCIP_CAMPO7_POSITION["901"], 23)

    def test_tucuman_position(self):
        """Tucumán (924) is at index 0."""
        self.assertEqual(SIRCIP_CAMPO7_POSITION["924"], 0)

    def test_chaco_position(self):
        """Chaco (906) is at index 18."""
        self.assertEqual(SIRCIP_CAMPO7_POSITION["906"], 18)

    def test_mendoza_position(self):
        """Mendoza (913) is at index 11."""
        self.assertEqual(SIRCIP_CAMPO7_POSITION["913"], 11)

    def test_all_24_jurisdictions_covered(self):
        """All 24 jurisdictions 901-924 are mapped."""
        self.assertEqual(len(SIRCIP_CAMPO7_POSITION), 24)
        for jc in range(901, 925):
            self.assertIn(str(jc), SIRCIP_CAMPO7_POSITION, "Missing JC=%s" % jc)

    def test_positions_are_unique(self):
        """Each jurisdiction has its own position in field 7."""
        positions = list(SIRCIP_CAMPO7_POSITION.values())
        self.assertEqual(len(positions), len(set(positions)), "Duplicated positions")

    def test_positions_range(self):
        """Positions are within 0-23: index 24 is the trailing '0'."""
        for jcode, pos in SIRCIP_CAMPO7_POSITION.items():
            self.assertGreaterEqual(pos, 0, "JC=%s has a negative position" % jcode)
            self.assertLessEqual(pos, 23, "JC=%s uses the reserved index 24 (always 0)" % jcode)

    def test_digit_caba_digit2(self):
        """CABA (index 23) reads digit 2 in the record design example."""
        fiscal_line = self._get_fiscal_pos_line()
        state_caba = self.env.ref("base.state_ar_c")
        campo7 = "5225355222512555552512420"
        digit = fiscal_line._get_sircip_campo7_digit(campo7, state_caba)
        self.assertEqual(digit, 2)

    def test_digit_cordoba_digit1(self):
        """Córdoba (904, index 20) reads digit 1 in the record design example."""
        fiscal_line = self._get_fiscal_pos_line()
        state_cordoba = self.env.ref("base.state_ar_x")
        campo7 = "5225355222512555552512420"
        digit = fiscal_line._get_sircip_campo7_digit(campo7, state_cordoba)
        self.assertEqual(digit, 1)

    def test_digit_empty_campo7(self):
        """An empty field 7 returns 0."""
        fiscal_line = self._get_fiscal_pos_line()
        state_caba = self.env.ref("base.state_ar_c")
        digit = fiscal_line._get_sircip_campo7_digit("", state_caba)
        self.assertEqual(digit, 0)

    def test_digit_no_state(self):
        """No delivery province returns 0."""
        fiscal_line = self._get_fiscal_pos_line()
        digit = fiscal_line._get_sircip_campo7_digit("5225355222512555552512420", False)
        self.assertEqual(digit, 0)

    def test_digit_non_adherida_province(self):
        """A province whose jurisdiction code is not mapped returns 0."""
        fiscal_line = self._get_fiscal_pos_line()
        sircip_state = self.env.ref("l10n_ar_sircip.state_ar_sircip")
        digit = fiscal_line._get_sircip_campo7_digit("5225355222512555552512420", sircip_state)
        self.assertEqual(digit, 0)
