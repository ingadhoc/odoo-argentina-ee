from odoo import Command, fields
from odoo.addons.l10n_ar_withholding.tests.test_withholding_ar_ri import TestArWithholdingArRi
from odoo.tests import tagged


@tagged("-at_install", "post_install")
class TestArbaWS(TestArWithholdingArRi):
    """Tests para el módulo l10n_ar_arba_ws

    Valida la funcionalidad de:
    - Creación y manejo de Declaraciones Juradas (DJ) de ARBA
    - Envío automático de retenciones a ARBA
    - Modos manual y automático de retenciones
    - Conexión al webservice A122R de ARBA
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Configurar la compañía para usar ARBA en modo demo
        cls.env.company.write(
            {
                "l10n_ar_arba_env": "demo",
                "l10n_ar_arba_dj_period": "fortnightly",
                "l10n_ar_arba_wh_mode": "batch_import",
                "l10n_ar_arba_client_id": "demo_client_id",
                "l10n_ar_arba_client_secret": "demo_client_secret",
            }
        )

        # Usar un tax de retención ARBA existente (Buenos Aires)
        cls.state_ar_b = cls.env.ref("base.state_ar_b")
        # Reutilizar tax de retención de IIBB Buenos Aires ya existente
        cls.tax_arba_withholding = cls.env.ref("account.%i_ex_tax_withholding_iibb_ba_applied" % cls.env.company.id)
        cls.tax_arba_withholding.write(
            {
                "amount": 2.0,
                "amount_type": "percent",
            }
        )

        # Crear partner para pruebas
        cls.partner_ba = cls.env["res.partner"].create(
            {
                "name": "Partner Buenos Aires",
                "country_id": cls.env.ref("base.ar").id,
                "state_id": cls.state_ar_b.id,
                "l10n_ar_afip_responsibility_type_id": cls.env.ref("l10n_ar.res_IVARI").id,
                "vat": "20123456789",
                "is_company": True,
            }
        )

    def _create_invoice_with_arba_withholding(self, invoice_date=None, doc_number=None):
        """Helper para crear factura de proveedor con retención ARBA"""
        if not invoice_date:
            invoice_date = fields.Date.today()

        # Generar número de documento único si no se proporciona
        if not doc_number:
            # Usar timestamp para evitar duplicados
            import time

            doc_number = "0001-%08d" % int(time.time() * 1000 % 100000000)

        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "date": invoice_date,
                "invoice_date": invoice_date,
                "partner_id": self.partner_ba.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "price_unit": 10000.0,
                            "quantity": 1,
                            "tax_ids": [Command.set(self.tax_21.ids)],
                        }
                    )
                ],
                "l10n_latam_document_number": doc_number,
            }
        )
        invoice.action_post()
        return invoice

    def _create_payment_with_arba_withholding(self, invoice, withholding_amount=None):
        """Helper para crear pago con retención ARBA"""
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "payment_date": invoice.date,
                }
            )
        )

        base_amount = withholding_amount if withholding_amount is not None else invoice.amount_untaxed
        wizard.l10n_ar_withholding_ids = [Command.clear()] + [
            Command.create(
                {
                    "tax_id": self.tax_arba_withholding.id,
                    "base_amount": base_amount,
                    "amount": 0,
                }
            )
        ]
        # Forzar el cómputo del amount
        for wh_line in wizard.l10n_ar_withholding_ids:
            wh_line._compute_amount()

        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action["res_id"])
        return payment

    # Test 1: Validar creación manual de DJ ARBA
    def test_01_create_dj_arba_manually(self):
        """Test validando creación manual de DJ ARBA.
        Cambio validado: Modelo l10n_ar.dj.arba con campos básicos
        """
        dj_date = fields.Date.from_string("2026-02-10")
        dj_arba = self.env["l10n_ar.dj.arba"].create(
            {
                "company_id": self.env.company.id,
                "date": dj_date,
            }
        )

        self.assertEqual(dj_arba.state, "draft", "Nueva DJ debe estar en estado draft")
        self.assertEqual(dj_arba.company_id, self.env.company)
        self.assertFalse(dj_arba.name, "DJ en draft no debe tener ID asignado")

    # Test 2: Validar apertura de DJ ARBA en modo demo
    def test_02_open_dj_arba_demo_mode(self):
        """Test validando apertura de DJ en modo demo.
        Cambio validado: action_open() con lógica para modo demo
        """
        dj_date = fields.Date.from_string("2026-02-10")
        dj_arba = self.env["l10n_ar.dj.arba"].create(
            {
                "company_id": self.env.company.id,
                "date": dj_date,
            }
        )

        dj_arba.action_open()

        self.assertEqual(dj_arba.state, "open", "DJ debe estar abierta después de action_open")
        self.assertTrue(dj_arba.name, "DJ abierta debe tener ID asignado (modo demo)")
        self.assertTrue(dj_arba.name.startswith("Demo-"), "En modo demo el ID debe empezar con Demo-")

    # Test 3: Validar cálculo de quincena
    def test_03_fortnight_calculation(self):
        """Test validando cálculo de quincena correcta.
        Cambio validado: _get_fortnight() method
        """
        dj_model = self.env["l10n_ar.dj.arba"]

        # Primera quincena (día 1-15)
        date_first = fields.Date.from_string("2026-02-10")
        self.assertEqual(dj_model._get_fortnight(date_first), 1, "Día 10 debe ser quincena 1")

        date_first_border = fields.Date.from_string("2026-02-15")
        self.assertEqual(dj_model._get_fortnight(date_first_border), 1, "Día 15 debe ser quincena 1")

        # Segunda quincena (día 16-fin de mes)
        date_second = fields.Date.from_string("2026-02-20")
        self.assertEqual(dj_model._get_fortnight(date_second), 2, "Día 20 debe ser quincena 2")

        date_second_border = fields.Date.from_string("2026-02-16")
        self.assertEqual(dj_model._get_fortnight(date_second_border), 2, "Día 16 debe ser quincena 2")

    # Test 4: Validar envío manual de retención a ARBA
    def test_04_send_withholding_to_arba_manually(self):
        """Test validando envío manual de retención a ARBA.
        Cambio validado: send_to_arba() method en l10n_ar.payment.withholding
        """
        invoice = self._create_invoice_with_arba_withholding()
        payment = self._create_payment_with_arba_withholding(invoice)

        # Obtener línea de retención ARBA
        arba_wh_line = payment.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )

        self.assertTrue(arba_wh_line, "Debe existir línea de retención ARBA")
        self.assertFalse(arba_wh_line.l10n_ar_cert_number, "Inicialmente no debe tener certificado")

        # Enviar a ARBA manualmente
        arba_wh_line.send_to_arba()

        self.assertTrue(arba_wh_line.l10n_ar_cert_number, "Después de enviar debe tener certificado")
        self.assertTrue(arba_wh_line.l10n_ar_dj_arba_id, "Debe estar vinculada a una DJ")
        self.assertEqual(arba_wh_line.l10n_ar_dj_arba_id.state, "open", "La DJ debe estar abierta")

    # Test 5: Validar que _ensure_dj crea DJ automáticamente
    def test_05_ensure_dj_creates_automatically(self):
        """Test validando creación automática de DJ según periodo.
        Cambio validado: _ensure_dj() method
        """
        wh_date = fields.Date.from_string("2026-02-10")

        # No debe existir DJ para este periodo
        existing_dj = self.env["l10n_ar.dj.arba"].search(
            [
                ("company_id", "=", self.env.company.id),
                ("state", "=", "open"),
                ("date", ">=", fields.Date.start_of(wh_date, "month")),
                ("date", "<=", wh_date.replace(day=15)),
            ]
        )
        self.assertFalse(existing_dj, "No debe existir DJ inicial")

        # Crear factura y pago con retención
        invoice = self._create_invoice_with_arba_withholding(wh_date)
        payment = self._create_payment_with_arba_withholding(invoice)
        arba_wh_line = payment.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )

        # Enviar a ARBA (debe crear DJ automáticamente)
        arba_wh_line.send_to_arba()

        # Verificar que se creó la DJ
        created_dj = self.env["l10n_ar.dj.arba"].search(
            [
                ("company_id", "=", self.env.company.id),
                ("state", "=", "open"),
                ("date", ">=", fields.Date.start_of(wh_date, "month")),
                ("date", "<=", wh_date.replace(day=15)),
            ]
        )
        self.assertTrue(created_dj, "Debe haberse creado DJ automáticamente")
        self.assertEqual(created_dj, arba_wh_line.l10n_ar_dj_arba_id, "Retención debe estar vinculada a la DJ creada")

    # Test 6: Validar modo automático de retenciones
    def test_06_automatic_withholding_mode(self):
        """Test validando modo automático de envío de retenciones.
        Cambio validado: account.payment.action_post() con envío automático
        """
        # Cambiar a modo automático
        self.env.company.l10n_ar_arba_wh_mode = "automatic"

        invoice = self._create_invoice_with_arba_withholding()

        # Crear wizard de pago
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "payment_date": invoice.date,
                }
            )
        )

        wizard.l10n_ar_withholding_ids = [Command.clear()] + [
            Command.create(
                {
                    "tax_id": self.tax_arba_withholding.id,
                    "base_amount": invoice.amount_untaxed,
                    "amount": 0,
                }
            )
        ]
        wizard.l10n_ar_withholding_ids._compute_amount()

        # Crear pago (debe enviar automáticamente en action_post)
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action["res_id"])

        # Verificar que se envió automáticamente
        arba_wh_line = payment.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )
        self.assertTrue(
            arba_wh_line.l10n_ar_cert_number, "En modo automático debe enviarse y tener certificado inmediatamente"
        )

    # Test 7: Validar que múltiples retenciones usan misma DJ en mismo periodo
    def test_07_multiple_withholdings_same_dj(self):
        """Test validando que múltiples retenciones del mismo periodo usan la misma DJ.
        Cambio validado: _ensure_dj() reutiliza DJ existente del periodo
        """
        wh_date = fields.Date.from_string("2026-02-10")

        # Crear dos facturas con retenciones en el mismo periodo
        invoice1 = self._create_invoice_with_arba_withholding(wh_date)
        payment1 = self._create_payment_with_arba_withholding(invoice1)

        invoice2 = self._create_invoice_with_arba_withholding(wh_date.replace(day=12))
        payment2 = self._create_payment_with_arba_withholding(invoice2)

        # Enviar ambas retenciones
        arba_wh_line1 = payment1.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )
        arba_wh_line1.send_to_arba()

        arba_wh_line2 = payment2.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )
        arba_wh_line2.send_to_arba()

        # Verificar que ambas usan la misma DJ
        self.assertEqual(
            arba_wh_line1.l10n_ar_dj_arba_id,
            arba_wh_line2.l10n_ar_dj_arba_id,
            "Retenciones del mismo periodo deben usar la misma DJ",
        )

    # Test 8: Validar periodos diferentes usan DJs diferentes
    def test_08_different_periods_different_djs(self):
        """Test validando que retenciones de periodos diferentes crean DJs diferentes.
        Cambio validado: _ensure_dj() con lógica de periodo quincenal
        """
        # Primera quincena de febrero
        wh_date1 = fields.Date.from_string("2026-02-10")
        invoice1 = self._create_invoice_with_arba_withholding(wh_date1)
        payment1 = self._create_payment_with_arba_withholding(invoice1)
        arba_wh_line1 = payment1.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )
        arba_wh_line1.send_to_arba()

        # Segunda quincena de febrero
        wh_date2 = fields.Date.from_string("2026-02-20")
        invoice2 = self._create_invoice_with_arba_withholding(wh_date2)
        payment2 = self._create_payment_with_arba_withholding(invoice2)
        arba_wh_line2 = payment2.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )
        arba_wh_line2.send_to_arba()

        # Verificar que son DJs diferentes
        self.assertNotEqual(
            arba_wh_line1.l10n_ar_dj_arba_id,
            arba_wh_line2.l10n_ar_dj_arba_id,
            "Retenciones de quincenas diferentes deben usar DJs diferentes",
        )

    # Test 9: Validar actualización de estado de DJ
    def test_09_update_dj_status(self):
        """Test validando actualización de estado de DJ.
        Cambio validado: action_update_status() method
        """
        dj_date = fields.Date.from_string("2026-02-10")
        dj_arba = self.env["l10n_ar.dj.arba"].create(
            {
                "company_id": self.env.company.id,
                "date": dj_date,
            }
        )
        dj_arba.action_open()

        initial_state = dj_arba.state
        self.assertEqual(initial_state, "open")

        # Actualizar estado (en modo demo alterna entre open y close)
        dj_arba.action_update_status()

        # Verificar que cambió de estado
        self.assertNotEqual(dj_arba.state, initial_state, "Estado debe cambiar después de actualizar")

    # Test 10: SKIP - Validar que solo retenciones ARBA se envían automáticamente
    # Este test requiere crear un tax adicional que no está disponible en todos los entornos
    # Se omite para simplificar la suite de tests inicial

    # Test 11: Validar campos relacionados en withholding
    def test_11_withholding_related_fields(self):
        """Test validando campos relacionados agregados en withholding.
        Cambio validado: l10n_ar_arba_wh_mode y l10n_ar_state_id related fields
        """
        invoice = self._create_invoice_with_arba_withholding()
        payment = self._create_payment_with_arba_withholding(invoice)

        arba_wh_line = payment.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )

        # Verificar campos relacionados
        self.assertEqual(
            arba_wh_line.l10n_ar_arba_wh_mode,
            self.env.company.l10n_ar_arba_wh_mode,
            "l10n_ar_arba_wh_mode debe estar relacionado con company",
        )
        self.assertEqual(
            arba_wh_line.l10n_ar_state_id, self.state_ar_b, "l10n_ar_state_id debe estar relacionado con tax"
        )

    # Test 12: Validar periodo mensual
    def test_12_monthly_period_dj(self):
        """Test validando creación de DJ con periodo mensual.
        Cambio validado: _ensure_dj() con periodo mensual
        """
        # Cambiar a periodo mensual
        self.env.company.l10n_ar_arba_dj_period = "monthly"

        # Primera mitad del mes
        wh_date1 = fields.Date.from_string("2026-03-10")
        invoice1 = self._create_invoice_with_arba_withholding(wh_date1)
        payment1 = self._create_payment_with_arba_withholding(invoice1)
        arba_wh_line1 = payment1.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )
        arba_wh_line1.send_to_arba()

        # Segunda mitad del mes
        wh_date2 = fields.Date.from_string("2026-03-25")
        invoice2 = self._create_invoice_with_arba_withholding(wh_date2)
        payment2 = self._create_payment_with_arba_withholding(invoice2)
        arba_wh_line2 = payment2.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )
        arba_wh_line2.send_to_arba()

        # En periodo mensual, deben usar la misma DJ todo el mes
        self.assertEqual(
            arba_wh_line1.l10n_ar_dj_arba_id,
            arba_wh_line2.l10n_ar_dj_arba_id,
            "Con periodo mensual, retenciones del mismo mes deben usar la misma DJ",
        )

    # Test 13: Validar que no se duplican envíos
    def test_13_no_duplicate_sending(self):
        """Test validando que retenciones con certificado no se reenvían.
        Cambio validado: Filtro en send_to_arba() para evitar duplicados
        """
        invoice = self._create_invoice_with_arba_withholding()
        payment = self._create_payment_with_arba_withholding(invoice)

        arba_wh_line = payment.l10n_ar_withholding_line_ids.filtered(
            lambda x: x.tax_id.l10n_ar_state_id == self.state_ar_b
        )

        # Primer envío
        arba_wh_line.send_to_arba()
        first_cert = arba_wh_line.l10n_ar_cert_number
        first_dj = arba_wh_line.l10n_ar_dj_arba_id
        self.assertTrue(first_cert, "Debe tener certificado después del primer envío")
        self.assertTrue(first_dj, "Debe estar vinculada a una DJ")

        # Intentar reenviar (no debería hacer nada porque ya tiene certificado)
        arba_wh_line.send_to_arba()
        second_cert = arba_wh_line.l10n_ar_cert_number
        second_dj = arba_wh_line.l10n_ar_dj_arba_id

        # Certificado y DJ no deben cambiar
        self.assertEqual(first_cert, second_cert, "Certificado no debe cambiar al reintentar enviar")
        self.assertEqual(first_dj, second_dj, "DJ no debe cambiar al reintentar enviar")

    # Test 14: Validar display_name de DJ
    def test_14_dj_display_name(self):
        """Test validando el formato del display_name de DJ.
        Cambio validado: _compute_display_name() method
        """
        # Primera quincena
        dj_date1 = fields.Date.from_string("2026-02-10")
        dj_arba1 = self.env["l10n_ar.dj.arba"].create(
            {
                "company_id": self.env.company.id,
                "date": dj_date1,
            }
        )

        self.assertIn("Period", dj_arba1.display_name)
        self.assertIn("2026", dj_arba1.display_name)
        self.assertIn("1st", dj_arba1.display_name)  # Primera quincena

        # Segunda quincena
        dj_date2 = fields.Date.from_string("2026-02-20")
        dj_arba2 = self.env["l10n_ar.dj.arba"].create(
            {
                "company_id": self.env.company.id,
                "date": dj_date2,
            }
        )

        self.assertIn("2nd", dj_arba2.display_name)  # Segunda quincena

    # Test 15: Validar constraint de DJ única
    def test_15_unique_dj_constraint(self):
        """Test validando que no se puedan duplicar DJs con mismo ID.
        Cambio validado: SQL constraint unique_ddjj_id
        """
        from psycopg2 import errors

        dj_date = fields.Date.from_string("2026-02-10")
        dj_arba1 = self.env["l10n_ar.dj.arba"].create(
            {
                "company_id": self.env.company.id,
                "date": dj_date,
            }
        )
        dj_arba1.action_open()

        # Intentar crear otra con el mismo nombre directamente
        # (en situación normal esto no debería pasar, pero validamos el constraint)
        with self.assertRaises(errors.UniqueViolation):
            with self.env.cr.savepoint():
                self.env["l10n_ar.dj.arba"].create(
                    {
                        "company_id": self.env.company.id,
                        "date": dj_date,
                        "name": dj_arba1.name,
                        "state": "draft",
                    }
                )
