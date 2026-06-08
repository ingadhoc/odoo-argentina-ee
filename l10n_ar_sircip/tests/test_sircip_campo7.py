##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.addons.l10n_ar_sircip.models.account_fiscal_position_l10n_ar_tax import (
    SIRCIP_CAMPO7_POSITION,
)
from odoo.tests import common


class TestSircipCampo7(common.TransactionCase):
    """Tests para la lógica del campo 7 del padrón SIRCIP.

    El campo 7 tiene 25 chars numéricos. Se lee de DERECHA a IZQUIERDA:
      - índice 24 (rightmost) = siempre '0', descartar
      - fórmula: índice = 924 - jurisdiction_code
      - valores dígito: 1=solo básica, 2=básica+sobretasa, 3=excluido,
                        4/5=básica+alícuota propia
    """

    def _get_fiscal_pos_line(self):
        """Crea un registro vacío del modelo para poder llamar los métodos."""
        # Crear posición fiscal de test
        fiscal_pos = self.env["account.fiscal.position"].create(
            {
                "name": "Test SIRCIP",
                "company_id": self.env.company.id,
            }
        )
        # Buscar impuesto SIRCIP No Inscripto de la compañía demo
        sircip_tax = self.env["account.tax"].search(
            [
                ("name", "ilike", "No Inscripto"),
                ("tax_group_id.name", "=", "SIRCIP"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if not sircip_tax:
            self.skipTest("No hay impuestos SIRCIP creados en la compañía demo")
        return self.env["account.fiscal.position.l10n_ar_tax"].create(
            {
                "fiscal_position_id": fiscal_pos.id,
                "default_tax_id": sircip_tax.id,
                "tax_type": "perception",
            }
        )

    # --- Tabla SIRCIP_CAMPO7_POSITION ---

    def test_position_formula(self):
        """Verifica que la fórmula índice = 924 - jurisdiction_code es correcta."""
        for jcode_str, idx in SIRCIP_CAMPO7_POSITION.items():
            jcode = int(jcode_str)
            expected = 924 - jcode
            self.assertEqual(
                idx,
                expected,
                "JC=%s debería estar en índice %s, no %s" % (jcode_str, expected, idx),
            )

    def test_caba_position(self):
        """CABA (jurisdicción 901) está en índice 23."""
        self.assertEqual(SIRCIP_CAMPO7_POSITION["901"], 23)

    def test_tucuman_position(self):
        """Tucumán (jurisdicción 924) está en índice 0."""
        self.assertEqual(SIRCIP_CAMPO7_POSITION["924"], 0)

    def test_chaco_position(self):
        """Chaco (jurisdicción 906) está en índice 18."""
        self.assertEqual(SIRCIP_CAMPO7_POSITION["906"], 18)

    def test_mendoza_position(self):
        """Mendoza (jurisdicción 913) está en índice 11."""
        self.assertEqual(SIRCIP_CAMPO7_POSITION["913"], 11)

    def test_all_24_jurisdictions_covered(self):
        """Los 24 jurisdiction_codes de 901-924 están en el mapa."""
        self.assertEqual(len(SIRCIP_CAMPO7_POSITION), 24)
        for jc in range(901, 925):
            self.assertIn(str(jc), SIRCIP_CAMPO7_POSITION, "Falta JC=%s" % jc)

    def test_positions_are_unique(self):
        """Cada jurisdicción ocupa una posición única en el campo 7."""
        positions = list(SIRCIP_CAMPO7_POSITION.values())
        self.assertEqual(len(positions), len(set(positions)), "Hay posiciones duplicadas")

    def test_positions_range(self):
        """Todas las posiciones están en el rango 0-23 (no usan el índice 24=zero)."""
        for jcode, pos in SIRCIP_CAMPO7_POSITION.items():
            self.assertGreaterEqual(pos, 0, "JC=%s tiene posición negativa" % jcode)
            self.assertLessEqual(pos, 23, "JC=%s usa el índice 24 reservado (siempre 0)" % jcode)

    # --- _get_sircip_campo7_digit ---

    def test_digit_caba_digit2(self):
        """Extrae dígito 2 para CABA (índice 23) del ejemplo del PDF."""
        fiscal_line = self._get_fiscal_pos_line()
        state_caba = self.env.ref("base.state_ar_c")
        # Ejemplo del PDF: campo7 = 5225355222512555552512420
        # índice 23 (CABA) = '2'
        campo7 = "5225355222512555552512420"
        digit = fiscal_line._get_sircip_campo7_digit(campo7, state_caba)
        self.assertEqual(digit, 2)

    def test_digit_cordoba_digit1(self):
        """Extrae dígito 1 para Córdoba (índice 20) del ejemplo del PDF."""
        fiscal_line = self._get_fiscal_pos_line()
        state_cordoba = self.env.ref("base.state_ar_x")
        # Ejemplo del PDF: campo7 = 5225355222512555552512420
        # índice 20 (Córdoba, JC=904) = '1'
        campo7 = "5225355222512555552512420"
        digit = fiscal_line._get_sircip_campo7_digit(campo7, state_cordoba)
        self.assertEqual(digit, 1)

    def test_digit_empty_campo7(self):
        """Campo 7 vacío retorna 0."""
        fiscal_line = self._get_fiscal_pos_line()
        state_caba = self.env.ref("base.state_ar_c")
        digit = fiscal_line._get_sircip_campo7_digit("", state_caba)
        self.assertEqual(digit, 0)

    def test_digit_no_state(self):
        """Sin estado retorna 0."""
        fiscal_line = self._get_fiscal_pos_line()
        digit = fiscal_line._get_sircip_campo7_digit("5225355222512555552512420", False)
        self.assertEqual(digit, 0)

    def test_digit_non_adherida_province(self):
        """Provincia sin jurisdiction_code en el mapa retorna 0."""
        fiscal_line = self._get_fiscal_pos_line()
        sircip_state = self.env.ref("l10n_ar_sircip.state_ar_sircip")
        digit = fiscal_line._get_sircip_campo7_digit("5225355222512555552512420", sircip_state)
        self.assertEqual(digit, 0)
