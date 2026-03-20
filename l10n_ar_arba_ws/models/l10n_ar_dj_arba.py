import json
import logging
import re
from datetime import datetime
from http import HTTPStatus

import requests
from markupsafe import Markup
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date, html_escape

WS_NAME = "A122R"

_logger = logging.getLogger(__name__)


class L10nArDjArba(models.Model):
    _name = "l10n_ar.dj.arba"
    _description = "ARBA DDJJ"
    _inherit = ["mail.thread.main.attachment", "mail.activity.mixin", "analytic.mixin"]

    name = fields.Char(help="Declaration ID returned by webservice", string="Id DDJJ", readonly=True)
    date = fields.Date(required=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    is_refund = fields.Boolean(
        string="It is annulment",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Open"),
            ("close", "Closed"),
        ],
        default="draft",
        tracking=True,
    )

    l10n_ar_withholding_ids = fields.One2many(
        "l10n_ar.payment.withholding",
        "l10n_ar_dj_arba_id",
        string="Withholdings",
        readonly=True,
    )

    open_date = fields.Datetime(readonly=True)
    due_date = fields.Datetime(readonly=True)
    close_date = fields.Datetime(readonly=True)

    _sql_constraints = [
        (
            "unique_ddjj_id",
            "UNIQUE(name)",
            "Error! Duplicate - The sworn statement already exists.",
        ),
    ]

    # Constrains

    @api.constrains("display_name", "company_id", "state")
    def unique_by_company_period_state(self):
        for ddjj in self:
            from_date, to_date = ddjj._find_dates(ddjj.date)
            other_ddjj_arba = self.search(
                [
                    ("company_id", "=", ddjj.company_id.id),
                    # We need to also have the state because we can a have valid open, close and draft one for the same period.
                    ("state", "=", ddjj.state),
                    ("date", ">=", from_date),
                    ("date", "<=", to_date),
                    ("id", "!=", ddjj.id),
                ],
                limit=1,
            )
            if other_ddjj_arba:
                raise UserError(
                    self.env._(
                        "Error when creating DDJJ ARBA, there is already one for the same period (%s) and company (%s)",
                        ddjj.display_name,
                        ddjj.company_id.name,
                    )
                )

    # Computes

    @api.depends("name", "date", "is_refund")
    def _compute_display_name(self):
        # TODO que escriba el Perido MesEscrito año y quincena (agregue si es rectificativa o no)
        to_compute = self.filtered("date")
        for rec in to_compute:
            name_month = format_date(self.env, rec.date, date_format="MMMM")
            n_fortnight = self.env._("1st") if rec._get_fortnight(rec.date) == 1 else self.env._("2nd")
            new_name = self.env._("Period %s %s - %s Fortnight", name_month, rec.date.year, n_fortnight)
            if rec.name:
                new_name += " **"
            rec.display_name = new_name
        (self - to_compute).display_name = "/"

    # Helpers

    @api.model
    def _create_withholding(self, wh_line):
        """Este metodo crea la retencion en ARBA via webservice
        y deja la info vinculada la linea de retencion

        Ejemplo del request
            * idDj SI id de la DDJJ se toma de la respuesta de Inicio
            * cuitContribuyente SI cuit del contribuyente retenido (N11) y debe
            ser un cuit válido.
            * cuitAgente SI cuit del agente que retiene (N11) tiene que
            coincidir con el cuit de inicio de la DDJJ
            * sucursal SI string <= 5, debiendo ser numéricos
            * alicuota SI Numérico (1 con 2 decimales) puede salir observada, lo que implica que NO se da de alta el comprobante
            * baseImponible SI Numérico (N15,2)
            * importeRetencion SI Numérico (N15,2)
            * razonSocialContribuyente SI String (50) – Apellido y Nombre o Razón Social del Contribuyente
            * fechaOperacion SI Datetime YYYY-MM-DDTHH:MM:SS.ms
            * dirección NO
                * calle NO String (50)
                * numero NO String (5)
                * piso NO String (5)
                * departamento NO String (5)
                * codigoPostal NO String (8)
                * localidad NO String (32)
                * provincia NO String (32)
        """
        ok_msg = self.env._("The withholding was reported to ARBA (%s) successfully")
        error_prefix = self.env._("Reporting withholding via webservice (Certificate number was not generated)")

        ddjj = self
        open_ddjj_error = False
        if not ddjj:
            try:
                ddjj = self._ensure_dj(wh_line.payment_id.date, wh_line.company_id)
                if ddjj.state != "open":
                    open_ddjj_error = self.env._("DDJJ could not be opened, the withholding cannot be created")
            except (UserError, ValidationError) as exp:
                self.env.cr.rollback()
                open_ddjj_error = str(exp)

        if open_ddjj_error or not ddjj:
            wh_line.payment_id.message_post(
                body=self.env._("ERROR trying to inform the withholding: ") + str(open_ddjj_error)
            )
            return

        self = ddjj
        env_type = self.company_id._get_arba_environment_type()

        if env_type == "demo":
            # Simular que nos conectamos y hacemos un comprobante dummy local
            wh_line.l10n_ar_cert_number = "Demo-%s" % fields.Datetime.now().strftime("%Y%m%d%H%M%S")
            wh_line.ref = wh_line.name  # almacenamos numero interno en el ref
            wh_line.name = wh_line.l10n_ar_cert_number
            wh_line.l10n_ar_dj_arba_id = self
            ok_msg = ok_msg % wh_line.l10n_ar_cert_number
            msg = self.env._("(DEMO MODE) %s", ok_msg)
            wh_line.payment_id.message_post(body=msg)
            self.message_post(body=msg)
            return

        # TODO commercial partner queremos usarlo?
        request_data = {
            "idDj": self.name,
            "cuitContribuyente": int(wh_line.payment_id.partner_id.ensure_vat()),
            "razonSocialContribuyente": wh_line.payment_id.partner_id.name,
            "cuitAgente": int(self.company_id.partner_id.ensure_vat()),
            "sucursal": 1,  # TODO revisar que valor string <= 5, debiendo ser numéricos
            "alicuota": wh_line.tax_id.amount,
            "baseImponible": wh_line.base_amount,
            "importeRetencion": wh_line.amount,
            "fechaOperacion": wh_line.payment_id.date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "nTransaccionAgente": re.sub("[^0-9]", "", wh_line.name),  # Obligatorio String(20)
        }

        response, error = self._process_arba_response(
            "POST", "/comprobante", env_type, self.env._("Send Withholding to ARBA"), request_data
        )

        if error:
            self._process_arba_error(error, error_prefix, wh_line.payment_id)
            return

        # Adjuntamos el numero de certificado al nombre de la retencion solo cuando realmente lo obtuvimos
        # Si esto no ocurre dejamos mensaje en el chatter
        if cert_number := response.get("nroEmision"):
            wh_line.l10n_ar_cert_number = cert_number
            wh_line.ref = wh_line.name  # almacenamos numero interno en el ref
            wh_line.name = cert_number
            wh_line.l10n_ar_dj_arba_id = self
            ok_msg = ok_msg % wh_line.l10n_ar_cert_number
            self.message_post(body=ok_msg)
            wh_line.payment_id.message_post(body=ok_msg)
        else:
            self._process_arba_error(response, error_prefix, wh_line.payment_id)

    @api.model
    def _find_dates(self, wh_date):
        if wh_date.day > 15:
            from_date = wh_date.replace(day=16)
            to_date = fields.Date.end_of(wh_date, "month")
        else:
            from_date = fields.Date.start_of(wh_date, "month")
            to_date = wh_date.replace(day=15)
        return from_date, to_date

    def _ensure_dj(self, wh_date, company):
        """Encontrar la declaracion jurada que corresponde, que este en el mismo periodo de la retención.

        :return: DDJJ ARBA recordset of the matching DDJJ for the given period"""
        from_date, to_date = self._find_dates(wh_date)
        dj_arba = self.search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "open"),
                ("date", ">=", from_date),
                ("date", "<=", to_date),
            ],
            limit=1,
        )
        if not dj_arba:
            dj_arba = self.create(
                {
                    "company_id": company.id,
                    "date": wh_date,
                }
            )
            dj_arba.action_open()
        return dj_arba

    def _get_fortnight(self, date):
        if date.day > 15:
            return 2
        return 1

    def _process_arba_ddjj_data(self, response):
        """t will receive the DDJJ dictionary with the values returned by the web service and will
        create and load them into Odoo in the respective fields.

        NOTE: Other keys that can be present and that we are not syncing

            'N_COMPRO_ARW': 13849241,
            'actividad': 6,
            'cantidadRetenciones': 0,
            'cuitAgente': 30506792165,
            'totalRetenciones': 0}
            'anio': 2026,
            'mes': 3,
            'quincena': 1,"""
        self.ensure_one()
        self.name = response.get("id")
        self.is_refund = response.get("rectificativa")
        if fechaCreacion := response.get("fechaCreacion"):
            self.open_date = datetime.fromisoformat(fechaCreacion[:26])
        if fechaVencimiento := response.get("fechaVencimiento"):
            self.due_date = datetime.fromisoformat(fechaVencimiento[:26])
        if fechaCierre := response.get("fechaCierre"):
            self.close_date = datetime.fromisoformat(fechaCierre[:26])
        if estado := response.get("estado"):
            self.state = "open" if estado == "Abierto" else "close"

    def _process_arba_error(self, error_obj, msg_prefix, record=None):
        """It Will process the response with a error code, will create a pretty html message and
        post it in the given record. If not record given will publish the message in the
        DDJJ ARBA chatter

        :param error_obj: could be a dictionary with the response or and string with an error
        :param msg_prefix: string to show as prefix before the processed ARBA info.
        :parma record: recordset where the message will be posted, if not set then will be posted
                        on the DDJJ"""
        record = record or self
        record.ensure_one()

        if isinstance(error_obj, dict):
            response = error_obj
            error_msg = self.env._(
                "<ul><li> STATUS %s</li><li>CODE %s</li><li>MESSAGE %s</li></ul>",
                str(html_escape(response.get("status")) or ""),
                str(html_escape(response.get("error")) or ""),
                str(html_escape(response.get("message")) or ""),
            )
        elif isinstance(error_obj, str):
            error_msg = self.env._("<br>Response: %s", str(html_escape(error_obj)))
        else:
            error_msg = self.env._("<br>Unknown: %s", str(html_escape(str(error_obj))))
        prefix_text = self.env._("ARBA ERROR") + (" " + msg_prefix if msg_prefix else " ")
        record.message_post(body=Markup(prefix_text + error_msg))
        _logger.error("ARBA WS ERROR: %s", prefix_text + error_msg)

    def _process_arba_response(self, method, url, env_type, msg, data=None):
        """Let us to have both clean response dictionary and string of errors if exists
        :return: tuple (response, error) -- type (dict, string)"""
        error = False
        connection = self.company_id._l10n_ar_get_connection(WS_NAME)
        url = connection._l10n_ar_get_afip_ws_url(WS_NAME, env_type) + url
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {connection.token}",
        }
        data = data or {}
        data = json.dumps(data)
        response = None
        try:
            response = requests.request(method, url, headers=headers, data=data, timeout=(45, 60))
        except Exception as exp:
            error = str(exp)

        if response and not HTTPStatus(response.status_code).is_success:
            res = response.json()
            error = f"{response.status_code} - {res.get('error')} {res.get('message')}"
        if error:
            self.message_post(body=self.env._("ERROR - %s:\n\n%s", msg, error))
            _logger.error("ARBA WS ERROR - %s: %s", msg, error)
        else:
            response = response.json()

        return response, error

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft_without_withholdings(self):
        non_draft_records = self.filtered(lambda record: record.state != "draft")
        if non_draft_records:
            raise UserError(self.env._("You can only delete DDJJ ARBA records in draft state."))

        records_with_withholdings = self.filtered("l10n_ar_withholding_ids")
        if records_with_withholdings:
            raise UserError(self.env._("You cannot delete a DDJJ ARBA that has withholding lines."))

    # Buttons

    def action_open(self):
        """Se conecta a ARBA y cera una la declaración jurada que quedan en estado abierto para que la
        podemos usar. Si todo va bien tendremos de respuesta un ID de declaracion y varios datos
        devueltos por ARBA que quedan guardados en la DDJJ en Odoo

        Si hay error, entonces la declaracion queda en estado Borrador, y deja detalle del error en el
        mensajeria de la declaración

        Ejemplos responses
        Codigo 200
        {
            "id": 0,
            "anio": 0,
            "mes": 0,
            "quincena": 0,
            "actividad": "string",
            "actividadId": 0,
            "fechaVencimiento": "2025-12-01T12:02:21.895Z",
            "rectificativa": 0,
            "fechaCierre": "2025-12-01T12:02:21.895Z",
            "fechaCreacion": "2025-12-01T12:02:21.895Z",
            "totalRetenciones": 0,
            "cantidadRetenciones": 0,
            "cuitAgente": 0,
            "razonSocialAgente": "string",
            "tieneLotePendiente": true,
            "tieneObservaciones": true,
            "tieneErrores": true,
            "N_COMPRO_ARW": 0
        }
        Codigo 400 o 500
        {
            "timestamp": "string",
            "status": 0,
            "error": "string",
            "message": "string",
            "stack": "string",
            "path": "string",
            "data": "string"
        }
        """
        self.ensure_one()
        env_type = self.company_id._get_arba_environment_type()
        ok_msg = self.env._("The declaration was successfully opened")

        if env_type == "demo":
            # Simular que nos conectamos y hacemos la declaracion pero modo dummy local
            self.write(
                {
                    "name": fields.Datetime.now().strftime("Demo-%Y%m%d%H%M%S"),
                    "state": "open",
                }
            )
            self.message_post(body=self.env._("(DEMO MODE) %s", ok_msg))
            return

        if self.name:
            return self.action_update_status()

        # Call webservice to open declaration
        request_params = {
            "cuitAgente": int(self.company_id.partner_id.ensure_vat()),
            "quincena": self._get_fortnight(self.date),
            "actividadId": 6,
            "anio": self.date.year,
            "mes": self.date.month,
        }
        response, error = self._process_arba_response(
            "POST", "/declaracionJurada", env_type, self.env._("Open Declaration"), request_params
        )
        error_prefix = self.env._("Error opening the declaration: DDJJ ID number was not generated")
        if error:
            self._process_arba_error(error, error_prefix)
            return

        if response.get("id"):
            self._process_arba_ddjj_data(response)
            self.state = "open"
            self.message_post(body=ok_msg)
        else:
            self._process_arba_error(response, error_prefix)

    def action_find_existing(self):
        """Si ya la declaracion esta iniciada y aun no esta en Odoo podemos ver de permitir crerla trayendo los datos
        basicos asi podemos usarla. esto es util sobre todo en tests"""
        self.ensure_one()
        url = f"/declaracionJurada?cuitAgente={int(self.company_id.partner_id.ensure_vat())}"
        if self.name:
            return

        ok_msg = self.env._("An existing DDJJ was successfully linked")
        env_type = self.company_id._get_arba_environment_type()
        if env_type == "demo":
            # Simular que nos conectamos y hacemos la declaracion pero modo dummy local
            self.write(
                {
                    "name": fields.Datetime.now().strftime("Demo-%Y%m%d%H%M%S"),
                    "state": "open",
                }
            )
            self.message_post(body=self.env._("(DEMO MODE) %s", ok_msg))
            return

        info = {
            "quincena": self._get_fortnight(self.date),
            "actividadId": 6,
            "anio": self.date.year,
            "mes": self.date.month,
        }
        for key, value in info.items():
            url += f"&{key}={value}"
        response, error = self._process_arba_response(
            "GET",
            url,
            env_type,
            self.env._("Get DDJJ Information"),
        )
        error_prefix = self.env._("Linking existing DDJJ:")
        if error:
            self._process_arba_error(error, error_prefix)
            return

        if not response:
            self._process_arba_error(self.env._("We did not receive any response"), error_prefix)
            return

        if isinstance(response, list):
            response = response[0]

        # Si obtenemos ID de DDJJ entonces llenamos los datos, sino lanzamos mensaje de error
        if response and response.get("id"):
            self._process_arba_ddjj_data(response)
            self.message_post(body=ok_msg)
        else:
            self._process_arba_error(response, error_prefix)

    def action_update_status(self):
        """Consulta y actualiza el estado de la declaración jurada en ARBA en el Odoo

        Ejemplo de los datos del request {
            "cuitAgente": self.company_id.partner_id.ensure_vat(),
            "quincena": self._get_fortnight(self.date),
            "actividadId": 6,
            "anio": self.date.year,
            "mes": self.date.month,
        }

        Ejemplo del response [
            {
                "id": 35684,
                "cuitAgente": 30506792165,
                "anio": 2026,
                "mes": 2,
                "quincena": 1,
                "totalRetenciones": 250,
                "cantidadRetenciones": 1,
                "estado": "Abierto",
                "N_COMPRO_ARW": 40021623,
                "actividad": 6
            }
        ]
        """
        self.ensure_one()
        env_type = self.company_id._get_arba_environment_type()
        ok_msg = self.env._("The DDJJ's status has been updated")
        if env_type == "demo":
            # Simular que nos conectamos y hacemos la declaracion pero modo dummy local
            self.state = "open" if self.state != "open" else "close"
            self.message_post(body=self.env._("(DEMO MODE) %s", ok_msg))
            return

        if not self.name:
            raise UserError(self.env._("You can only update status from informed DDJJ"))

        response, error = self._process_arba_response(
            "GET",
            f"/declaracionJurada?cuitAgente={int(self.company_id.partner_id.ensure_vat())}&idDj={int(self.name)}",
            env_type,
            self.env._("Update Declaration"),
        )
        prefix_error = self.env._("Updating status:")
        if error:
            self._process_arba_error(error, prefix_error)
            return

        if not response:
            self._process_arba_error(self.env._("We did not receive any response"), prefix_error)
            return

        if isinstance(response, list):
            response = response[0]

        # Si obtenemos ID de DDJJ entonces llenamos los datos, sino lanzamos mensaje de error
        if response and response.get("id"):
            dj_state = response.get("estado")
            self.state = "open" if dj_state == "Abierto" else "close"
            self.message_post(body=ok_msg)
        else:
            self._process_arba_error(response, prefix_error)
