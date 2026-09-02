##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import io
import zipfile

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestL10nArAccountReportsCommon

DATE_FROM = "2035-01-01"
DATE_TO = "2035-01-31"

CABA_LINES = ["caba_withholdings_line", "caba_perceptions_line"]
SANTA_FE_LINES = ["santa_fe_withholdings_line", "santa_fe_perceptions_line"]
TUCUMAN_LINES = ["tucuman_withholdings_line", "tucuman_perceptions_line"]

# Los archivos que exporta el módulo. Del prefijo salen el reporte
# (``l10n_ar_<prefijo>_report``), su handler y las líneas de la liquidación.
#
#   only      recorte cuando dos archivos se reparten los apuntes de la misma
#             línea: CABA y Tucumán separan las notas de crédito
#   records   registros esperados, contados sobre el escenario de abajo
#   header    renglones del archivo que no son un apunte
#
# Mendoza no está: su archivo no se puede generar (ver ``test_open_bugs.py``).
# Cuando se corrija hay que sumarlo acá.
#
# prefijo  | método del archivo | líneas del reporte | only | records | header
TXT_FILES = [
    # PBA: las retenciones van por lote A122R y las percepciones tienen dos
    # archivos —general y actividad 7— sobre los mismos apuntes.
    ("pba", "pba_alta_ret_lote_a122r_01032026_txt", ["pba_withholdings_line"], None, 1, 0),
    ("pba", "pba_perc_desde_01032026_txt", ["pba_perceptions_line"], None, 1, 0),
    ("pba", "pba_perc_act_7_desde_01032026_txt", ["pba_perceptions_line"], None, 1, 0),
    # CABA informa retenciones y percepciones en un archivo y las NC en otro.
    ("caba", "caba_ret_perc_txt", CABA_LINES, "invoices", 3, 0),
    ("caba", "nc_caba_ret_perc_txt", CABA_LINES, "refunds", 1, 0),
    # SICORE es una sola presentación: ganancias, retención de IVA y percepción
    # de IVA salen intercaladas en el mismo archivo.
    (
        "sicore",
        "sicore_book_export_files_to_txt",
        ["profits_line", "vat_withholding_line", "vat_perception_line"],
        None,
        3,
        0,
    ),  # noqa: E501
    ("sifere", "sifere_ret_txt", ["sifere_withholdings_line"], None, 1, 0),
    ("sifere", "sifere_perc_txt", ["sifere_perceptions_line"], None, 1, 0),
    # Los despachos de importación no se importan en el aplicativo: el archivo
    # es un aviso para cargarlos a mano y arranca con un renglón de texto.
    ("sifere", "sifere_despachos_txt", ["sifere_despachos_line"], None, 1, 1),
    # SIRCAR entrega un zip con un archivo por jurisdicción.
    ("sircar", "sircar_ret_txt", ["sircar_withholdings_line"], None, 3, 0),
    ("sircar", "sircar_perc_txt", ["sircar_perceptions_line"], None, 2, 0),
    ("misiones", "misiones_ret_txt", ["misiones_withholdings_line"], None, 1, 0),
    ("misiones", "misiones_perc_txt", ["misiones_perceptions_line"], None, 1, 0),
    ("santa_fe", "santa_fe_ret_perc_txt", SANTA_FE_LINES, None, 2, 0),
    # Tucumán presenta tres archivos: dos con todos los apuntes y uno solo con
    # las notas de crédito.
    ("tucuman", "tucuman_datos_txt", TUCUMAN_LINES, None, 4, 0),
    ("tucuman", "tucuman_retper_txt", TUCUMAN_LINES, None, 4, 0),
    ("tucuman", "tucuman_ncfact_txt", TUCUMAN_LINES, "refunds", 1, 0),
    ("iva", "ret_iva_sufridas_txt", ["iva_withholdings_line"], None, 1, 0),
    ("iva", "perc_iva_sufridas_txt", ["iva_perceptions_line"], None, 1, 0),
]


@tagged("post_install_l10n", "post_install", "-at_install")
class TestTxtLineCount(TestL10nArAccountReportsCommon):
    """Lo que informa la liquidación es lo que sale en el archivo.

    Es el control que hace el usuario antes de presentar: mira cuántas
    percepciones y retenciones tiene el período, baja el TXT y cuenta los
    renglones. Si no coinciden, la presentación va incompleta (o con datos de
    más) y el archivo igual sale bien formado, así que nada falla.

    Un solo escenario cubre diecinueve de los veinte archivos porque es el
    mismo control. Tiene operaciones de varias jurisdicciones a la vez y en los
    dos sentidos, que es lo que hace que un dominio flojo se note: si un
    archivo se lleva un apunte de otra provincia o de otro régimen, no da.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Percepciones de IIBB aplicadas en ventas, una por jurisdicción.
        for state_code, day in (("C", "05"), ("B", "06"), ("S", "07"), ("N", "08"), ("T", "09")):
            cls._create_invoice(cls.perception_taxes[state_code], "2035-01-%s" % day)
        # Percepción de IVA: la informa SICORE junto con las retenciones.
        cls._create_invoice(cls.tax_perception_vat, "2035-01-10")

        # Notas de crédito de CABA y de Tucumán, que tienen archivo propio.
        refunded_caba = cls._create_invoice(cls.perception_taxes["C"], "2035-01-11")
        cls._create_refund(refunded_caba, cls.perception_taxes["C"], "2035-01-12")
        refunded_tucuman = cls._create_invoice(cls.perception_taxes["T"], "2035-01-13")
        cls._create_refund(refunded_tucuman, cls.perception_taxes["T"], "2035-01-14")

        # Las seis retenciones de IIBB practicadas en el mismo pago a proveedor.
        cls._create_payment_with_withholdings(
            cls.env["account.tax"].union(*cls.withholding_taxes.values()), "2035-01-15", price_unit=100000.0
        )
        # Retenciones nacionales (IVA y ganancias), las que informa SICORE. La
        # base es grande porque ganancias tiene mínimo no sujeto a retención.
        cls._create_payment_with_withholdings(
            cls.tax_withholding_vat + cls.tax_withholding_earnings, "2035-01-16", price_unit=cls.earnings_base
        )

        # Percepciones sufridas en compras: IIBB va a SIFERE, IVA al archivo de
        # IVA sufrido.
        cls._create_invoice(cls.perception_suffered_taxes["C"], "2035-01-17", move_type="in_invoice")
        cls._create_invoice(cls.tax_perception_vat_suffered, "2035-01-18", move_type="in_invoice")
        # Retenciones sufridas en una cobranza.
        cls._create_payment_with_withholdings(
            cls.withholding_suffered_iibb + cls.withholding_suffered_vat,
            "2035-01-19",
            move_type="out_invoice",
            price_unit=100000.0,
        )
        # Despacho de importación: SIFERE lo separa del resto de las sufridas.
        cls._create_invoice(
            cls.perception_suffered_taxes["S"],
            "2035-01-20",
            move_type="in_invoice",
            l10n_latam_document_type_id=cls.env.ref("l10n_ar.dc_desp_imp").id,
            document_number="1234567890123456",
        )

    def _reported_move_lines(self, report, prefix, options, line_names, only=None):
        """Los apuntes que informa la liquidación en las líneas indicadas.

        Salen del mismo método que usa el botón de auditoría del reporte
        (``_get_audit_line_domain``): es lo que ve el usuario cuando hace clic
        en el importe de la liquidación.
        """
        move_lines = self.env["account.move.line"]
        for line_name in line_names:
            report_line = self.env.ref("l10n_ar_account_reports.l10n_ar_%s_report_%s" % (prefix, line_name))
            expression = report_line.expression_ids.filtered(lambda expr: expr.label == "balance")
            for column_group_key in options["column_groups"]:
                move_lines |= self.env["account.move.line"].search(
                    report._get_audit_line_domain(
                        report._get_column_group_options(options, column_group_key),
                        expression,
                        {"calling_line_dict_id": report._get_generic_line_id("account.report.line", report_line.id)},
                    )
                )
        if only:
            is_refund = only == "refunds"
            move_lines = move_lines.filtered(lambda line: (line.move_id.move_type == "out_refund") is is_refund)
        return move_lines

    def _txt_records(self, file_content):
        """Los renglones del archivo, sea un TXT o el zip que entrega SIRCAR."""
        if file_content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(file_content)) as archive:
                return [
                    record
                    for name in archive.namelist()
                    for record in archive.read(name).decode("ISO-8859-1").splitlines()
                ]
        return file_content.decode("ISO-8859-1").splitlines()

    def test_los_renglones_del_txt_son_los_apuntes_de_la_liquidacion(self):
        for prefix, method_name, line_names, only, expected, header in TXT_FILES:
            with self.subTest(method_name):
                report = self.env.ref("l10n_ar_account_reports.l10n_ar_%s_report" % prefix)
                options = self._report_options(report, DATE_FROM, DATE_TO)
                move_lines = self._reported_move_lines(report, prefix, options, line_names, only)

                # El escenario primero: si esto falla, el archivo se está
                # probando con otros datos y la comparación de abajo no dice nada.
                self.assertEqual(
                    len(move_lines),
                    expected,
                    "%s: la liquidación informa %s apunte(s) y el escenario tiene %s: %s"
                    % (method_name, len(move_lines), expected, move_lines.mapped("tax_line_id.name")),
                )

                handler = self.env["l10n_ar.%s.report.handler" % prefix]
                records = self._txt_records(getattr(handler, method_name)(options)["file_content"])
                self.assertEqual(
                    len(records) - header,
                    len(move_lines),
                    "%s: la liquidación informa %s apunte(s) y el archivo trae %s registro(s)\n%s"
                    % (method_name, len(move_lines), len(records) - header, "\n".join(r[:80] for r in records)),
                )
                self.assert_latin1_safe(records, method_name)

    def test_ningun_archivo_se_genera_con_asientos_no_publicados(self):
        """Un archivo con retenciones en borrador se presenta al organismo con
        datos que todavía no existen, y después hay que rectificar."""
        for prefix, method_name, *_rest in TXT_FILES:
            with self.subTest(method_name):
                report = self.env.ref("l10n_ar_account_reports.l10n_ar_%s_report" % prefix)
                options = dict(self._report_options(report, DATE_FROM, DATE_TO), all_entries=True)
                with self.assertRaises(UserError):
                    getattr(self.env["l10n_ar.%s.report.handler" % prefix], method_name)(options)
