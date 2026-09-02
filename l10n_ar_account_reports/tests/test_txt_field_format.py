##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.addons.l10n_ar_account_reports.models.helpers import (
    format_amount,
    get_pos_and_number,
    remove_accents_and_dieresis,
)
from odoo.tests import TransactionCase, tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestTxtFieldFormat(TransactionCase):
    """Formato de los campos que comparten todos los archivos de declaración.

    Son las funciones de ``models/helpers.py``: las usan los diez handlers, así
    que un error acá corre las posiciones de todos los archivos a la vez.
    """

    def test_los_importes_llenan_el_campo_y_el_signo_no_lo_agranda(self):
        for label, amount, padding, decimals, sep, expected in (
            # Importe de percepción de PBA: 13 posiciones con separador coma.
            ("percepción", 1234.56, 13, 2, ",", "0000001234,56"),
            # Nota de crédito: el "-" entra en la primera posición y el largo
            # no cambia, que es lo que hace que el campo siguiente no se corra.
            ("nota de crédito", -1234.56, 13, 2, ",", "-000001234,56"),
            # Alícuota de CABA: 5 posiciones.
            ("alícuota", 3.0, 5, 2, ",", "03,00"),
            # Sin separador el campo es todo numérico y mantiene el largo.
            ("sin separador", 1234.56, 16, 2, "", "0000000000123456"),
            ("cero", 0.0, 13, 2, ",", "0000000000,00"),
        ):
            with self.subTest(label):
                result = format_amount(amount, padding, decimals, sep)
                self.assertEqual(result, expected)
                self.assertEqual(len(result), padding, "el campo tiene que medir exactamente %s" % padding)

    def test_el_numero_de_comprobante_se_parte_en_punto_de_venta_y_numero(self):
        for label, full_number, expected in (
            ("con guion", "0001-00000001", ("0001", "00000001")),
            # Sin guion no hay punto de venta que informar.
            ("sin guion", "12345", ("0", "12345")),
            ("con letras", "A0001-00000123", ("0001", "00000123")),
        ):
            with self.subTest(label):
                self.assertEqual(get_pos_and_number(full_number), expected)

    def test_la_razon_social_se_informa_sin_acentos(self):
        self.assertEqual(remove_accents_and_dieresis("Ñandú Perón S.A."), "Nandu Peron S.A.")
