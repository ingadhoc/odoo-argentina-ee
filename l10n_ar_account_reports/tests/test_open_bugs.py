##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
"""Hallazgos abiertos: tests que documentan bugs vivos del módulo.

Salieron de escribir esta suite y todavía no tienen fix. Afirman el
comportamiento correcto —la especificación dice qué tiene que pasar— y por eso
quedan en rojo. La clase va tagueada ``-standard`` para no teñir el build de
runbot: al corregir el bug hay que sacar su test de acá y llevarlo a la suite
que corresponde (el de Mendoza, a la tabla de ``test_txt_line_count.py``).
"""

from odoo.tests import tagged

from .common import TestL10nArAccountReportsCommon

# Largos de la especificación SAREPE (doc/Mendoza/SAREPE.pdf): CUIT formateado,
# denominación, fecha de comprobante, número de comprobante, fecha de la
# retención, base imponible, alícuota e importe retenido.
MENDOZA_RECORD_WIDTH = 13 + 80 + 8 + 12 + 8 + 15 + 5 + 15


@tagged("post_install_l10n", "post_install", "-at_install", "-standard")
class TestOpenBugs(TestL10nArAccountReportsCommon):
    def test_el_archivo_de_retenciones_de_mendoza_se_puede_generar(self):
        """``mendoza_report.py:102`` usa la variable ``name``, que solo se
        asigna dentro del ``if len(line.name) > 12`` de la línea 97. Con la
        secuencia de retención por defecto (8 dígitos) el nombre nunca pasa de
        12 caracteres, así que si es la primera retención del archivo revienta
        con ``UnboundLocalError``, y si vino después de una de más de 12
        informa el número de comprobante de la retención anterior: el archivo
        sale bien formado y con el dato de otro contribuyente. La
        especificación SAREPE pide rellenar con ceros a la izquierda.
        """
        payment = self._create_payment_with_withholdings(self.withholding_taxes["M"], "2035-01-10")
        move_lines = self._tax_move_lines(payment.move_id, self.withholding_taxes["M"])
        self.assertTrue(move_lines, "el escenario tiene que dejar el apunte de la retención")

        records = self.env["l10n_ar.mendoza.report.handler"]._get_mendoza_txt_content(move_lines)

        self.assertEqual(len(records), len(move_lines), "el archivo tiene que informar la retención del período")
        self.assert_fixed_width_records(records, MENDOZA_RECORD_WIDTH, "retención de Mendoza")
        # CUIT del retenido con guiones en las primeras 13 posiciones, y la
        # denominación completada con blancos a la derecha hasta 80.
        record = records[0]
        self.assertEqual(record[:13], self.partner_perceived.l10n_ar_formatted_vat)
        self.assertEqual(record[13:93].rstrip(), self.partner_perceived.name)
