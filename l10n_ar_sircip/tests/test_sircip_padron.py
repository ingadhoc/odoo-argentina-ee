##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common

# 5 líneas del padrón de demo: letras A, B, F, X y un CUIT no presente
SAMPLE_PADRON = (
    "periodo,cuit,razon_social_contri,jurisdiccion_sede,crc,alicuota_unica_letra,campo7\n"
    "202602,30684401250,EMPRESA F,922,25,F,5214252222222225522522550\n"
    "202602,20181117533,EMPRESA A,904,84,A,5224252222222225522512550\n"
    "202602,30712330216,EMPRESA X,901,34,X,5225252122222225522522540\n"
    "202602,20076105139,EMPRESA B,902,14,B,5224242222222125522512440\n"
    "202602,30710125909,EMPRESA V SOBRETASA,921,78,V,4214241111111114411411440\n"
)


class TestSircipPadron(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sircip_state = cls.env.ref("l10n_ar_sircip.state_ar_sircip")
        cls.padron = cls.env["res.company.jurisdiction.padron"].create(
            {
                "company_id": cls.env.company.id,
                "state_id": cls.sircip_state.id,
                "l10n_ar_padron_from_date": fields.Date.from_string("2026-02-01"),
                "l10n_ar_padron_to_date": fields.Date.from_string("2026-02-28"),
                "filename": "test_padron.txt",
                "file_padron": base64.b64encode(SAMPLE_PADRON.encode("latin-1")).decode(),
            }
        )

    # --- check_state_id ---

    def test_check_state_id_allows_sircip_province(self):
        """El constraint check_state_id permite la provincia ficticia SIRCIP."""
        # Si se llegó aquí sin ValidationError, el setUpClass ya pasó el constraint.
        self.assertTrue(self.padron.id)

    def test_check_state_id_rejects_non_sircip(self):
        """El constraint check_state_id rechaza provincias que no son SIRCIP ni ARBA/SF."""
        state_cordoba = self.env.ref("base.state_ar_x")
        with self.assertRaises(ValidationError):
            self.env["res.company.jurisdiction.padron"].create(
                {
                    "company_id": self.env.company.id,
                    "state_id": state_cordoba.id,
                    "l10n_ar_padron_from_date": fields.Date.from_string("2026-02-01"),
                    "l10n_ar_padron_to_date": fields.Date.from_string("2026-02-28"),
                    "filename": "test.txt",
                    "file_padron": base64.b64encode(b"dummy").decode(),
                }
            )

    # --- _get_sircip_aliquot ---

    def _make_partner(self, vat):
        return self.env["res.partner"].create(
            {
                "name": "Test Partner %s" % vat,
                "vat": vat,
                "l10n_latam_identification_type_id": self.env.ref("l10n_ar.it_cuit").id,
            }
        )

    def test_aliquot_letra_f(self):
        """Letra F → 0.30%."""
        partner = self._make_partner("30684401250")
        is_in, aliquot, campo7, crc = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 0.30)
        self.assertEqual(crc, "25")
        self.assertEqual(len(campo7), 25)

    def test_aliquot_letra_a(self):
        """Letra A → 0.00%."""
        partner = self._make_partner("20181117533")
        is_in, aliquot, campo7, crc = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 0.00)

    def test_aliquot_letra_x(self):
        """Letra X → 5.00%."""
        partner = self._make_partner("30712330216")
        is_in, aliquot, campo7, crc = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 5.00)

    def test_aliquot_letra_b(self):
        """Letra B → 0.01%."""
        partner = self._make_partner("20076105139")
        is_in, aliquot, campo7, crc = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 0.01)

    def test_cuit_not_in_padron(self):
        """CUIT no presente en el padrón retorna is_in_padron=False."""
        # CUIT válido del padrón demo que NO está en SAMPLE_PADRON (5 líneas)
        partner = self._make_partner("20294199153")
        is_in, aliquot, campo7, crc = self.padron._get_sircip_aliquot(partner)
        self.assertFalse(is_in)
        self.assertEqual(aliquot, 0.0)
        self.assertEqual(campo7, "")

    def test_campo7_length(self):
        """El campo 7 extraído del padrón tiene exactamente 25 caracteres."""
        partner = self._make_partner("30684401250")
        _, _, campo7, _ = self.padron._get_sircip_aliquot(partner)
        self.assertEqual(len(campo7), 25, "El campo 7 debe tener 25 chars")

    def test_campo7_rightmost_is_zero(self):
        """El carácter más a la derecha del campo 7 es siempre '0'."""
        partner = self._make_partner("30684401250")
        _, _, campo7, _ = self.padron._get_sircip_aliquot(partner)
        self.assertEqual(campo7[-1], "0", "El primer char (rightmost) del campo 7 debe ser '0'")

    # --- Provincias adheridas etapa 1 ---

    def test_etapa1_provinces_have_is_sircip_true(self):
        """Las 8 provincias de Etapa 1 tienen l10n_ar_is_sircip=True."""
        # Chaco=H, Jujuy=Y, Mendoza=M, Río Negro=R, Salta=A, San Juan=J,
        # Santiago del Estero=G, Tierra del Fuego=V
        etapa1_codes = ["H", "Y", "M", "R", "A", "J", "G", "V"]
        states = self.env["res.country.state"].search(
            [
                ("country_id.code", "=", "AR"),
                ("code", "in", etapa1_codes),
            ]
        )
        self.assertEqual(len(states), len(etapa1_codes))
        for state in states:
            self.assertTrue(
                state.l10n_ar_is_sircip,
                "Provincia %s (code=%s) debe tener l10n_ar_is_sircip=True" % (state.name, state.code),
            )

    def test_non_etapa1_provinces_have_is_sircip_false(self):
        """Provincias no adheridas (ej. Corrientes) tienen l10n_ar_is_sircip=False."""
        state_corrientes = self.env.ref("base.state_ar_w")  # Corrientes, no adherida
        self.assertFalse(state_corrientes.l10n_ar_is_sircip)
