##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64

from odoo import fields
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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Los impuestos SIRCIP se crean solo para empresas con plan de cuentas AR.
        # Cambiamos la compañía activa a company_ri donde existen los datos SIRCIP.
        company_ri = cls.env.ref("base.company_ri")
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[company_ri.id]))

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
        """CABA (jurisdicción 901) está en índgitice 23."""
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

    # --- _get_sircip_extra_taxes dígitos 4/5 ---

    def test_digit4_with_existing_partner_tax(self):
        """Dígito 4: usa partner.tax existente para la provincia de entrega."""
        fiscal_line = self._get_fiscal_pos_line()
        state_cordoba = self.env.ref("base.state_ar_x")
        partner = self.env["res.partner"].create(
            {
                "name": "Test partner digit4",
                "vat": "30683021209",
                "l10n_latam_identification_type_id": self.env.ref("l10n_ar.it_cuit").id,
            }
        )
        # Crear un tax no-SIRCIP para Córdoba y cachearlo en partner.tax
        cordoba_tax = self.env["account.tax"].create(
            {
                "name": "P. IIBB Córdoba Test 1.5%",
                "amount": 1.5,
                "type_tax_use": "sale",
                "company_id": self.env.company.id,
                "l10n_ar_state_id": state_cordoba.id,
            }
        )
        self.env["l10n_ar.partner.tax"].create(
            {
                "partner_id": partner.id,
                "tax_id": cordoba_tax.id,
                "from_date": "2026-02-01",
                "to_date": "2026-02-28",
            }
        )
        from odoo import fields as f

        result = fiscal_line._get_sircip_provincial_tax(state_cordoba, partner, f.Date.from_string("2026-02-15"))
        self.assertEqual(result, cordoba_tax)

    def test_digit4_no_provincial_rate_raises(self):
        """Dígito 4 sin alícuota provincial configurada lanza UserError."""
        from odoo import fields as f
        from odoo.exceptions import UserError

        fiscal_line = self._get_fiscal_pos_line()
        state_formosa = self.env.ref("base.state_ar_p")  # Formosa, poco configurada
        partner = self.env["res.partner"].create(
            {
                "name": "Test partner sin tasa provincial",
                "vat": "30683013184",
                "l10n_latam_identification_type_id": self.env.ref("l10n_ar.it_cuit").id,
            }
        )
        with self.assertRaises(UserError):
            fiscal_line._get_sircip_provincial_tax(state_formosa, partner, f.Date.from_string("2026-02-15"))

    def test_extra_taxes_digit1_returns_empty(self):
        """Dígito 1: sin impuestos extra."""
        fiscal_line = self._get_fiscal_pos_line()
        result = fiscal_line._get_sircip_extra_taxes(1, self.env.ref("base.state_ar_c"))
        self.assertFalse(result)

    def test_extra_taxes_digit2_returns_sobretasa(self):
        """Dígito 2: retorna el impuesto de sobrealícuota SIRCIP."""
        fiscal_line = self._get_fiscal_pos_line()
        result = fiscal_line._get_sircip_extra_taxes(2, self.env.ref("base.state_ar_c"))
        self.assertTrue(result)
        self.assertIn("Sobre Alícuota", result.name)


class TestSircipDigit45Flow(common.TransactionCase):
    """Tests del flujo completo de _get_tax_from_ws para dígitos 4 y 5 del campo 7.

    Dígitos 4/5: tasa básica SIRCIP + alícuota propia de la provincia de entrega.
    Se usa Chaco (JC=906, idx=924-906=18) como provincia de entrega.
    Se usa marzo 2026 para no solapar con el padrón de TestSircipPadron (feb 2026).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company_ri = cls.env.ref("base.company_ri")
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[company_ri.id]))

        cls.sircip_state = cls.env.ref("l10n_ar_sircip.state_ar_sircip")
        cls.chaco_state = cls.env.ref("base.state_ar_h")  # Chaco, adherida (l10n_ar_is_sircip=True)

        # Padrón con 2 CUITs: dígito 4 y dígito 5 en Chaco (idx=18).
        # campo7: 2222222222222222224222220 → idx[18]='4'
        # campo7: 2222222222222222225222220 → idx[18]='5'
        padron_content = (
            "periodo,cuit,razon_social_contri,jurisdiccion_sede,crc,alicuota_unica_letra,campo7\n"
            "202603,20042155455,DIGIT4 CHACO,901,34,T,2222222222222222224222220\n"
            "202603,33686664649,DIGIT5 CHACO,922,59,T,2222222222222222225222220\n"
        )
        cls.padron = cls.env["res.company.jurisdiction.padron"].create(
            {
                "company_id": cls.env.company.id,
                "state_id": cls.sircip_state.id,
                "l10n_ar_padron_from_date": fields.Date.from_string("2026-03-01"),
                "l10n_ar_padron_to_date": fields.Date.from_string("2026-03-31"),
                "filename": "test_digit45_padron.txt",
                "file_padron": base64.b64encode(padron_content.encode("latin-1")).decode(),
            }
        )

        # Posición fiscal SIRCIP + línea con default_tax No Inscripto
        cls.fp = cls.env["account.fiscal.position"].search(
            [("name", "=", "Percepción - SIRCIP"), ("company_id", "=", cls.env.company.id)],
            limit=1,
        )
        cls.sircip_no_inscripto = cls.env["account.tax"].search(
            [
                ("name", "ilike", "No Inscripto"),
                ("tax_group_id.name", "=", "SIRCIP"),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )

        # Partners con los CUITs del padrón, domicilio en Chaco
        cls.partner_digit4 = cls.env["res.partner"].create(
            {
                "name": "Test Digit 4 Chaco",
                "vat": "20042155455",
                "l10n_latam_identification_type_id": cls.env.ref("l10n_ar.it_cuit").id,
                "state_id": cls.chaco_state.id,
                "country_id": cls.env.ref("base.ar").id,
            }
        )
        cls.partner_digit5 = cls.env["res.partner"].create(
            {
                "name": "Test Digit 5 Chaco",
                "vat": "33686664649",
                "l10n_latam_identification_type_id": cls.env.ref("l10n_ar.it_cuit").id,
                "state_id": cls.chaco_state.id,
                "country_id": cls.env.ref("base.ar").id,
            }
        )

        # Impuesto provincial Chaco (no-SIRCIP) pre-cacheado para ambos partners.
        # _get_sircip_provincial_tax lo encuentra vía l10n_ar.partner.tax.
        cls.chaco_tax = cls.env["account.tax"].create(
            {
                "name": "P. IIBB Chaco Test 1.5%",
                "amount": 1.5,
                "type_tax_use": "sale",
                "company_id": cls.env.company.id,
                "l10n_ar_state_id": cls.chaco_state.id,
            }
        )
        for partner in (cls.partner_digit4, cls.partner_digit5):
            cls.env["l10n_ar.partner.tax"].create(
                {
                    "partner_id": partner.id,
                    "tax_id": cls.chaco_tax.id,
                    "from_date": "2026-03-01",
                    "to_date": "2026-03-31",
                }
            )

    def _get_sircip_fiscal_pos_line(self):
        """Obtiene o crea la línea de posición fiscal SIRCIP (webservice=padron)."""
        if not self.fp or not self.sircip_no_inscripto:
            self.skipTest("Posición fiscal o impuesto SIRCIP No Inscripto no disponibles")
        existing = self.env["account.fiscal.position.l10n_ar_tax"].search(
            [
                ("fiscal_position_id", "=", self.fp.id),
                ("default_tax_id.l10n_ar_state_id", "=", self.sircip_state.id),
                ("webservice", "=", "padron"),
            ],
            limit=1,
        )
        if existing:
            return existing
        return self.env["account.fiscal.position.l10n_ar_tax"].create(
            {
                "fiscal_position_id": self.fp.id,
                "default_tax_id": self.sircip_no_inscripto.id,
                "tax_type": "perception",
                "webservice": "padron",
            }
        )

    def test_digit4_returns_sircip_and_provincial_tax(self):
        """Dígito 4: _get_tax_from_ws retorna tasa básica SIRCIP + alícuota provincial Chaco."""
        fiscal_line = self._get_sircip_fiscal_pos_line()

        # El partner tiene state_id=Chaco → _get_delivery_state lo usa como fallback.
        # Chaco tiene l10n_ar_is_sircip=True → se usa para calcular el dígito del campo 7.
        date = fields.Date.from_string("2026-03-15")
        result = fiscal_line._get_tax_from_ws(self.partner_digit4, date)

        self.assertGreaterEqual(len(result), 2, "Dígito 4 debe retornar al menos 2 impuestos")

        sircip_taxes = result.filtered(lambda t: t.tax_group_id.name == "SIRCIP")
        self.assertTrue(sircip_taxes, "Debe haber al menos un impuesto del grupo SIRCIP")

        self.assertIn(self.chaco_tax, result, "La alícuota provincial de Chaco debe estar en el resultado")

    def test_digit5_returns_sircip_and_provincial_tax(self):
        """Dígito 5: igual que dígito 4 — retorna tasa SIRCIP + alícuota provincial Chaco."""
        fiscal_line = self._get_sircip_fiscal_pos_line()

        date = fields.Date.from_string("2026-03-15")
        result = fiscal_line._get_tax_from_ws(self.partner_digit5, date)

        self.assertGreaterEqual(len(result), 2, "Dígito 5 debe retornar al menos 2 impuestos")

        sircip_taxes = result.filtered(lambda t: t.tax_group_id.name == "SIRCIP")
        self.assertTrue(sircip_taxes, "Debe haber al menos un impuesto del grupo SIRCIP")

        self.assertIn(self.chaco_tax, result, "La alícuota provincial de Chaco debe estar en el resultado")

    def test_ensure_sircip_tax_sets_delivery_state_in_name_and_field(self):
        """_ensure_sircip_tax crea un impuesto con la provincia de entrega en el nombre y l10n_ar_state_id."""
        fiscal_line = self._get_sircip_fiscal_pos_line()

        tax = fiscal_line._ensure_sircip_tax(3.0, "T", self.chaco_state)

        # El nombre incluye la provincia de entrega
        self.assertIn(self.chaco_state.name, tax.name, "El nombre debe incluir la provincia de entrega")

        # La jurisdicción apunta a la provincia de entrega (no a la ficticia SIRCIP)
        self.assertEqual(
            tax.l10n_ar_state_id,
            self.chaco_state,
            "l10n_ar_state_id debe apuntar a Chaco, no a la provincia ficticia SIRCIP",
        )
