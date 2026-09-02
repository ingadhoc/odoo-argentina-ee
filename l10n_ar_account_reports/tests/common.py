##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command, fields
from odoo.addons.l10n_ar_withholding.tests.test_withholding_ar_ri import TestArWithholdingArRi

# Datos de régimen que los archivos exigen en el impuesto: sin el código de
# régimen (SIRCAR, IVA) o el artículo e inciso (Santa Fe) el handler frena
# antes de escribir el primer registro. Es configuración de la base, no
# comportamiento a probar.
PERCEPTION_REGIME = {
    "l10n_ar_code": "001",
    "api_articulo_inciso_calculo_percepcion": "001",
    "api_codigo_articulo_percepcion": "021",
}
WITHHOLDING_REGIME = {
    "l10n_ar_code": "112",
    "api_articulo_inciso_calculo_retencion": "001",
    "api_codigo_articulo_retencion": "001",
}

# Impuestos del plan AR por jurisdicción, con la alícuota que se les pone: el
# plan los trae en 0 y así no se puede verificar ningún importe.
PERCEPTIONS_APPLIED = {"C": "caba", "B": "ba", "S": "sf", "N": "mi", "T": "tn"}
WITHHOLDINGS_APPLIED = {"C": "caba", "B": "ba", "S": "sf", "N": "ms", "M": "mza", "T": "t"}
PERCEPTIONS_SUFFERED = {"C": "caba", "S": "sf"}


class TestL10nArAccountReportsCommon(TestArWithholdingArRi):
    """Escenario común de las suites del módulo.

    Los helpers son ``classmethod`` porque el escenario se arma una vez por
    clase: los archivos TXT informan todo lo que hay en el período, así que un
    documento creado en un test entra en el archivo de los demás.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Percepciones de IIBB aplicadas en ventas.
        cls.perception_taxes = {
            code: cls._setup_perception("ri_tax_percepcion_iibb_%s_aplicada" % slug)
            for code, slug in PERCEPTIONS_APPLIED.items()
        }
        # Retenciones de IIBB practicadas en pagos a proveedores.
        cls.withholding_taxes = {
            code: cls._setup_withholding("ex_tax_withholding_iibb_%s_applied" % slug, amount=2.0)
            for code, slug in WITHHOLDINGS_APPLIED.items()
        }
        # Percepciones sufridas (las que le hacen a la compañía en sus compras).
        cls.perception_suffered_taxes = {
            code: cls._setup_perception("ri_tax_percepcion_iibb_%s_sufrida" % slug)
            for code, slug in PERCEPTIONS_SUFFERED.items()
        }

        # Impuestos nacionales, sin jurisdicción: son los que informa SICORE.
        cls.tax_perception_vat = cls._setup_perception("ri_tax_percepcion_iva_aplicada")
        cls.tax_perception_vat_suffered = cls._setup_perception("ri_tax_percepcion_iva_sufrida")
        cls.tax_withholding_vat = cls._setup_withholding("ex_tax_withholding_vat_applied")
        # Ganancias tiene mínimo no sujeto a retención: con bases chicas el
        # importe da cero y el registro no se informa.
        cls.tax_withholding_earnings = cls._company_tax("ex_tax_withholding_profits_regimen_112_insc")
        cls.tax_withholding_earnings.l10n_ar_withholding_sequence_id = cls.tax_wth_seq
        cls.earnings_base = 500000.0

        # El plan AR no trae retenciones sufridas con jurisdicción ni de IVA:
        # se arman copiando las practicadas y dándolas vuelta.
        cls.withholding_suffered_iibb = cls.withholding_taxes["C"].copy(
            {"name": "Ret IIBB CABA sufrida (test)", "l10n_ar_withholding_payment_type": "customer"}
        )
        cls.withholding_suffered_vat = cls.tax_withholding_vat.copy(
            {"name": "Ret IVA sufrida (test)", "l10n_ar_withholding_payment_type": "customer"}
        )

        cls.journal_bank = cls.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", cls.company_ri.id)], limit=1
        )
        # Contacto con todos los datos fiscales que piden los archivos: sin
        # esto los handlers frenan antes del primer registro.
        cls.partner_perceived = cls.env["res.partner"].create(
            {
                "name": "Perceived Partner SA",
                "is_company": True,
                "street": "Corrientes 1234",
                "city": "Rosario",
                "zip": "2000",
                "state_id": cls.env.ref("base.state_ar_s").id,
                "country_id": cls.env.ref("base.ar").id,
                "l10n_latam_identification_type_id": cls.env.ref("l10n_ar.it_cuit").id,
                "vat": "30710158254",
                "l10n_ar_afip_responsibility_type_id": cls.env.ref("l10n_ar.res_IVARI").id,
                "l10n_ar_gross_income_type": "local",
                "l10n_ar_gross_income_number": "901-99999999",
            }
        )
        cls._document_number_seq = 0

    # ------------------------------------------------------------------
    # Escenario
    # ------------------------------------------------------------------
    @classmethod
    def _company_tax(cls, template_code):
        """Los impuestos del plan se instalan con el id de la compañía de prefijo."""
        return cls.env.ref("account.%i_%s" % (cls.company_ri.id, template_code))

    @classmethod
    def _setup_perception(cls, template_code, amount=3.0):
        tax = cls._company_tax(template_code)
        tax.write(dict(PERCEPTION_REGIME, amount=amount, amount_type="percent"))
        return tax

    @classmethod
    def _setup_withholding(cls, template_code, amount=3.0):
        tax = cls._company_tax(template_code)
        tax.write(
            dict(
                WITHHOLDING_REGIME,
                amount=amount,
                amount_type="percent",
                l10n_ar_withholding_sequence_id=cls.tax_wth_seq.id,
            )
        )
        return tax

    @classmethod
    def _next_document_number(cls):
        cls._document_number_seq += 1
        return "0001-%08d" % cls._document_number_seq

    @classmethod
    def _create_invoice(cls, taxes=None, date=None, price_unit=1000.0, document_number=None, **vals):
        """Comprobante publicado con los impuestos indicados."""
        invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner_perceived.id,
                "date": date,
                "invoice_date": date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": cls.product_a.id,
                            "price_unit": price_unit,
                            "tax_ids": [Command.set((cls.tax_21 + (taxes or cls.env["account.tax"])).ids)],
                        }
                    )
                ],
                **vals,
            }
        )
        invoice.l10n_latam_document_number = document_number or cls._next_document_number()
        invoice.action_post()
        return invoice

    @classmethod
    def _create_refund(cls, invoice, taxes, date):
        """Nota de crédito con su percepción y el comprobante que corrige.

        No se usa ``_reverse_moves``: la reversión recalcula los impuestos
        desde la posición fiscal y se pierde la percepción, que es justamente
        lo que estos archivos informan.
        """
        return cls._create_invoice(
            taxes,
            date,
            move_type="out_refund",
            l10n_latam_document_type_id=cls.env.ref("l10n_ar.dc_a_nc").id,
            reversed_entry_id=invoice.id,
        )

    @classmethod
    def _create_payment_with_withholdings(cls, taxes, date, price_unit=1000.0, **vals):
        """Pago con retenciones, del lado que indique el comprobante.

        Con ``in_invoice`` (default) son las que la compañía practica a un
        proveedor; con ``out_invoice``, las que le practican a la compañía.
        """
        vals.setdefault("move_type", "in_invoice")
        invoice = cls._create_invoice(date=date, price_unit=price_unit, **vals)
        payment = (
            cls.env["account.payment"]
            .with_context(**invoice.action_register_payment()["context"])
            .create({"journal_id": cls.journal_bank.id, "amount": invoice.amount_total, "date": date})
        )
        payment.l10n_ar_withholding_line_ids = [Command.clear()] + [
            Command.create({"tax_id": tax.id, "base_amount": price_unit}) for tax in taxes
        ]
        # Sin el recálculo queda el importe que arrastra el registro de pagos.
        payment.l10n_ar_withholding_line_ids._compute_amount()
        payment.action_post()
        cls.env.flush_all()
        return payment

    @classmethod
    def _report_options(cls, report, date_from, date_to):
        """Las opciones que consumen los handlers, pedidas al reporte.

        Se piden al reporte y no se arman a mano para que el test use el mismo
        diccionario que la pantalla.
        """
        return report.get_options(
            previous_options={
                "date": {
                    "date_from": fields.Date.to_string(fields.Date.to_date(date_from)),
                    "date_to": fields.Date.to_string(fields.Date.to_date(date_to)),
                    "filter": "custom",
                    "mode": "range",
                },
            }
        )

    @classmethod
    def _tax_move_lines(cls, moves, tax):
        """Los apuntes de impuesto de un comprobante o pago, para un impuesto dado."""
        return moves.mapped("line_ids").filtered(lambda line: line.tax_line_id == tax)

    # ------------------------------------------------------------------
    # Invariantes de los archivos de declaración
    # ------------------------------------------------------------------
    def assert_fixed_width_records(self, records, width, ctx=""):
        """Cada registro mide lo que fija la especificación y corta con CRLF.

        Los organismos leen por posición: un carácter de más o de menos no
        falla, corre los campos siguientes e informa el dato de otro campo.
        """
        for index, record in enumerate(records, start=1):
            self.assertTrue(record.endswith("\r\n"), "%s: el registro %s no termina en CRLF" % (ctx, index))
            self.assertEqual(
                len(record),
                width + 2,
                "%s: el registro %s mide %s y la especificación pide %s (+CRLF).\n%r"
                % (ctx, index, len(record) - 2, width, record),
            )

    def assert_latin1_safe(self, records, ctx=""):
        """Ningún carácter del registro se pierde al codificar en ISO-8859-1.

        Los handlers codifican con ``errors="ignore"``: un carácter fuera de
        latin-1 no da error, se cae del archivo y corre las posiciones siguientes.
        """
        for index, record in enumerate(records, start=1):
            dropped = [char for char in record if char.encode("ISO-8859-1", "ignore") == b""]
            self.assertFalse(
                dropped,
                "%s: el registro %s pierde %s carácter(es) al codificar en ISO-8859-1: %s"
                % (ctx, index, len(dropped), dropped),
            )
