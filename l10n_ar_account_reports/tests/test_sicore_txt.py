##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.exceptions import RedirectWarning
from odoo.tests import tagged

from .common import TestL10nArAccountReportsCommon

# Largo del registro SICORE según el aplicativo SICORE v9.0 r22 (doc/Sicore/).
# Retenciones y percepciones comparten largo: es un único archivo.
SICORE_RECORD_WIDTH = 145


@tagged("post_install_l10n", "post_install", "-at_install")
class TestSicoreTxt(TestL10nArAccountReportsCommon):
    """Arquetipo de layout posicional: el registro de SICORE campo por campo.

    Los diez handlers del módulo escriben archivos de ancho fijo que el
    organismo lee por posición, así que un campo corrido no falla: informa el
    dato de otro campo. Verificar las posiciones de los diez layouts es un PR
    por familia; acá queda SICORE completo como arquetipo —es el que usan todas
    las bases— y los otros nueve quedan cubiertos a nivel de cantidad de
    renglones y codificación por ``test_txt_line_count.py``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.handler = cls.env["l10n_ar.sicore.report.handler"]

    def test_registro_de_retencion_de_ganancias(self):
        """El registro identifica el impuesto por el tipo de retención (0217
        ganancias), el régimen por el código del impuesto y el comprobante por
        el tipo de pago."""
        payment = self._create_payment_with_withholdings(
            self.tax_withholding_earnings, "2035-01-10", price_unit=self.earnings_base
        )
        move_lines = self._tax_move_lines(payment.move_id, self.tax_withholding_earnings)
        self.assertTrue(move_lines, "el escenario tiene que dejar el apunte de la retención de ganancias")

        records = [content for *_key, content in self.handler._get_sicore_withholding_content(move_lines)]

        self.assert_fixed_width_records(records, SICORE_RECORD_WIDTH, "retención de ganancias")
        record = records[0]
        # Pago a proveedor: código de comprobante 06.
        self.assertEqual(record[0:2], "06")
        self.assertEqual(record[2:12], "10/01/2035")
        # Número de comprobante: 16 posiciones, solo dígitos.
        self.assertTrue(record[12:28].isdigit(), "el número de comprobante tiene que salir numérico")
        # Ganancias es el impuesto 0217 y el régimen sale del código del impuesto.
        self.assertEqual(record[44:48], "0217")
        self.assertEqual(record[48:51], self.tax_withholding_earnings.l10n_ar_code)
        # Código de operación 1 = retención, condición 01 para ganancias.
        self.assertEqual(record[51:52], "1")
        self.assertEqual(record[76:78], "01")
        # Base e importe son campos distintos: ganancias descuenta el mínimo no
        # sujeto a retención, así que el importe no es base por alícuota.
        withholding = payment.l10n_ar_withholding_line_ids
        self.assertEqual(record[52:66], "%014.2f" % self.earnings_base)
        self.assertEqual(record[79:93], "%014.2f" % withholding.amount)
        self.assertNotEqual(
            withholding.amount,
            self.earnings_base,
            "el importe retenido no puede ser la base: son campos distintos del registro",
        )
        # Porcentaje de exclusión fijo, tipo y número de documento del retenido,
        # certificado original en ceros.
        self.assertEqual(record[93:99], "000.00")
        self.assertEqual(record[109:111], "80")
        self.assertEqual(record[111:131].rstrip(), self.partner_perceived.vat)
        self.assertEqual(record[131:145], "0" * 14)

    def test_registro_de_percepcion_de_iva(self):
        """La percepción de IVA usa el impuesto 0767 y el código de operación 2,
        y el comprobante sale del tipo de documento."""
        invoice = self._create_invoice(self.tax_perception_vat, "2035-01-11")
        move_lines = self._tax_move_lines(invoice, self.tax_perception_vat)
        self.assertTrue(move_lines, "el escenario tiene que dejar el apunte de la percepción de IVA")

        records = [content for *_key, content in self.handler._get_sicore_perception_content(move_lines)]

        self.assert_fixed_width_records(records, SICORE_RECORD_WIDTH, "percepción de IVA")
        record = records[0]
        # Factura de cliente: código de comprobante 01.
        self.assertEqual(record[0:2], "01")
        self.assertEqual(record[2:12], "11/01/2035")
        # 5 posiciones de punto de venta y 11 de número.
        self.assertEqual(record[12:17], "00001")
        self.assertEqual(record[17:28], "%011d" % int(invoice.l10n_latam_document_number.split("-")[1]))
        # IVA es el impuesto 0767 y el código de operación 2 es percepción.
        self.assertEqual(record[44:48], "0767")
        self.assertEqual(record[51:52], "2")

    def test_no_se_informa_un_retenido_sin_cuit(self):
        """Control positivo compartido por todos los archivos: sin CUIT el
        registro sale con el campo vacío y corre todas las posiciones
        siguientes, así que hay que frenar antes de escribirlo."""
        partner = self.partner_perceived.copy({"name": "Retenido sin CUIT", "vat": False})
        payment = self._create_payment_with_withholdings(
            self.tax_withholding_earnings, "2035-01-12", partner_id=partner.id, price_unit=self.earnings_base
        )
        move_lines = self._tax_move_lines(payment.move_id, self.tax_withholding_earnings)

        with self.assertRaises(RedirectWarning):
            self.handler._get_sicore_withholding_content(move_lines)
