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
        # Switch to company_ri (plan AR) so SIRCIP data exists.
        company_ri = cls.env.ref("base.company_ri")
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[company_ri.id]))
        cls.sircip_state = cls.env.ref("l10n_ar_sircip.state_ar_sircip")
        cls.month_start = fields.Date.today().replace(day=1)
        cls.month_end = fields.Date.end_of(cls.month_start, "month")
        cls.padron = cls.env["res.company.jurisdiction.padron"].create(
            {
                "company_id": cls.env.company.id,
                "state_id": cls.sircip_state.id,
                "l10n_ar_padron_from_date": cls.month_start,
                "l10n_ar_padron_to_date": cls.month_end,
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
                    "l10n_ar_padron_from_date": self.month_start,
                    "l10n_ar_padron_to_date": self.month_end,
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
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 0.30)
        self.assertEqual(crc, "25")
        self.assertEqual(len(campo7), 25)

    def test_aliquot_letra_a(self):
        """Letra A → 0.00%."""
        partner = self._make_partner("20181117533")
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 0.00)

    def test_aliquot_letra_x(self):
        """Letra X → 5.00%."""
        partner = self._make_partner("30712330216")
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 5.00)

    def test_aliquot_letra_b(self):
        """Letra B → 0.01%."""
        partner = self._make_partner("20076105139")
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 0.01)

    def test_cuit_not_in_padron(self):
        """CUIT no presente en el padrón retorna is_in_padron=False."""
        # CUIT válido del padrón demo que NO está en SAMPLE_PADRON (5 líneas)
        partner = self._make_partner("20294199153")
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertFalse(is_in)
        self.assertEqual(aliquot, 0.0)
        self.assertEqual(campo7, "")

    def test_campo7_length(self):
        """El campo 7 extraído del padrón tiene exactamente 25 caracteres."""
        partner = self._make_partner("30684401250")
        _, _, campo7, _, _ = self.padron._get_sircip_aliquot(partner)
        self.assertEqual(len(campo7), 25, "El campo 7 debe tener 25 chars")

    def test_campo7_rightmost_is_zero(self):
        """El carácter más a la derecha del campo 7 es siempre '0'."""
        partner = self._make_partner("30684401250")
        _, _, campo7, _, _ = self.padron._get_sircip_aliquot(partner)
        self.assertEqual(campo7[-1], "0", "El primer char (rightmost) del campo 7 debe ser '0'")

    # --- Auto-selección de la posición fiscal ---

    def test_fiscal_position_has_correct_configuration(self):
        """La posición fiscal SIRCIP tiene la configuración correcta para auto-selección.

        Para que se auto-seleccione en facturas necesita:
        - auto_apply=True
        - country_id=AR (aplica a todos los partners argentinos)
        - sequence=9999 (última, no compite con posiciones provinciales específicas)
        - l10n_ar_afip_responsibility_type_ids contiene IVA RI
        """
        ivari = self.env.ref("l10n_ar.res_IVARI", raise_if_not_found=False)
        self.assertTrue(ivari, "l10n_ar.res_IVARI no encontrado — verificar que l10n_ar esté instalado")

        fp = self.env["account.fiscal.position"].search(
            [("name", "=", "Percepción - SIRCIP"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        self.assertTrue(
            fp,
            "Posición fiscal 'Percepción - SIRCIP' no encontrada — "
            "debe crearse en el post_init_hook al instalar el módulo con empresa de plan AR",
        )

        self.assertTrue(fp.auto_apply, "auto_apply debe ser True para que se aplique automáticamente en facturas")
        self.assertEqual(fp.sequence, 9999, "sequence debe ser 9999 (última en ejecutarse)")
        self.assertEqual(fp.country_id, self.env.ref("base.ar"), "country_id debe ser AR")
        self.assertIn(
            ivari,
            fp.l10n_ar_afip_responsibility_type_ids,
            "l10n_ar_afip_responsibility_type_ids debe incluir IVA RI — "
            "sin esto la posición no se auto-selecciona en facturas de clientes RI",
        )

    # --- Plantillas de impuestos del post_init_hook ---

    def test_hook_tax_templates(self):
        """El hook deja una plantilla por tipo de registro de la DDJJ, con la cuenta y la etiqueta que usa el
        diario de liquidación, y el grupo con el código de tributo AFIP de percepción IIBB (07)."""
        templates = (
            self.env["account.tax"]
            .with_context(active_test=False)
            .search([("company_id", "=", self.env.company.id), ("l10n_ar_sircip_record_type", "!=", False)])
        )
        self.assertEqual(set(templates.mapped("l10n_ar_sircip_record_type")), {"1", "4", "5"})
        tag = self.env.ref("l10n_ar_sircip.tag_perc_iibb_sircip_aplicada")
        for tax in templates:
            tax_line = tax.invoice_repartition_line_ids.filtered(lambda r: r.repartition_type == "tax")
            self.assertTrue(tax_line.account_id, "%s sin cuenta" % tax.name)
            self.assertIn(tag, tax_line.tag_ids)
        self.assertEqual(templates.tax_group_id.l10n_ar_tribute_afip_code, "07")
