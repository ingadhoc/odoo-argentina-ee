import json
import re
from datetime import datetime
from http import HTTPStatus

import requests
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

WS_NAME = "A122R"


class L10nArDjArba(models.Model):
    _name = "l10n_ar.dj.arba"
    _description = "Declaración Jurada ARBA"
    _inherit = ["mail.thread.main.attachment", "mail.activity.mixin", "analytic.mixin"]

    name = fields.Char(help="Declaration ID returned by webservice", string="Id DJ", readonly=True)
    date = fields.Date(required=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    is_refund = fields.Boolean()
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

    _unique_ddjj_id = models.Constraint(
        "unique(name, company_id)",
        "Error! DDJJ ARBA already exists.",
    )

    # Computes

    @api.depends("name", "date", "is_refund")
    def _compute_display_name(self):
        # TODO que escriba el Perido MesEscrito año y quincena (agregue si es rectificativa o no)
        to_compute = self.filtered("date")
        for rec in to_compute:
            name_month = format_date(self.env, rec.date, date_format="MMMM")
            n_fortnight = self.env._("1st") if rec._get_fortnight(rec.date) == 1 else self.env._("2nd")
            rec.display_name = self.env._("Period %s %s - %s Fortnight", name_month, rec.date.year, n_fortnight)
        (self - to_compute).display_name = "/"

    # Helpers

    @api.model
    def _create_withholding(self, wh_line):
        """Este metodo crea la retencion en ARBA via webservice
        y deja la info vinculada la linea de retencion

        Ejemplo del request
            * idDj SI id de la DJ se toma de la respuesta de InicioDJ
            * cuitContribuyente SI cuit del contribuyente retenido (N11) y debe
            ser un cuit válido.
            * cuitAgente SI cuit del agente que retiene (N11) tiene que
            coincidir con el cuit de inicio de la DJ
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
        if not self:
            self = self._ensure_dj(wh_line.payment_id.date, wh_line.company_id)

        env_type = self.company_id._get_arba_environment_type()

        if env_type == "demo":
            # Simular que nos conectamos y hacemos un comprobante dummy local
            wh_line.l10n_ar_cert_number = "CERT-ARBA-Demo-%s" % fields.Datetime.now().strftime("%Y%m%d%H%M%S")
            wh_line.name = f"{wh_line.l10n_ar_cert_number} ({wh_line.name})"
            msg = f"(MODO DEMO) Fue informada Retención en ARBA ({wh_line.l10n_ar_cert_number})"
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
            "fechaOperacion": fields.Datetime.now().strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            ),  # wh_line.payment_id.date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            "nTransaccionAgente": re.sub("[^0-9]", "", wh_line.name),  # Obligatorio String(20)
        }
        response, error = self._process_arba_response(
            "POST", "/comprobante", env_type, "Enviar Retencion a ARBA", request_data
        )
        if error:
            wh_line.payment_id.message_post(body="Error al enviar retencion a ARBA: " + error)
            return

        wh_line.l10n_ar_dj_arba_id = self
        wh_line.l10n_ar_cert_number = response.get("nroEmision")
        wh_line.name = f"{wh_line.l10n_ar_cert_number} ({wh_line.name})"
        msg = f"Fue informada Retención en ARBA ({wh_line.l10n_ar_cert_number})"
        self.message_post(body=msg)
        wh_line.payment_id.message_post(body=msg)

    def _ensure_dj(self, wh_date, company):
        """Encontrar la declaracion jurada que corresponde, que este abierta y que este en el
        mismo periodo.
        Si no existe entonces genera una automaticamente"""

        period_type = company.l10n_ar_arba_dj_period
        if period_type == "monthly":
            from_date = fields.Date.start_of(wh_date, "month")
            to_date = fields.Date.end_of(wh_date, "month")
        elif period_type == "fortnightly":
            if wh_date.day > 15:
                from_date = wh_date.replace(day=16)
                to_date = fields.Date.end_of(wh_date, "month")
            else:
                from_date = fields.Date.start_of(wh_date, "month")
                to_date = wh_date.replace(day=15)
        else:
            raise UserError("ARBA DJ Period not implemented yet %s" % period_type)

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

    def _process_arba_response(self, method, url, env_type, msg, data=None):
        error = False
        connection = self.company_id._l10n_ar_get_connection(WS_NAME)
        url = connection._l10n_ar_get_afip_ws_url(WS_NAME, env_type) + url
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {connection.token}",
        }
        data = data or {}
        data = json.dumps(data)
        try:
            response = requests.request(method, url, headers=headers, data=data, timeout=(10, 60))
        except Exception as exp:
            error = str(exp)

        if response and not HTTPStatus(response.status_code).is_success:
            res = response.json()
            error = f"{response.status_code} - {res.get('error')} {res.get('message')}"
        if error:
            self.message_post(body=f"ERROR al {msg}:\n\n{error}")
        else:
            response = response.json()

        return response, error

    # Buttons

    def action_open(self):
        """Abre la declaración jurada en ARBA

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
        if env_type == "demo":
            # Simular que nos conectamos y hacemos la declaracion pero modo dummy local
            self.write(
                {
                    "name": fields.Datetime.now().strftime("Demo-%Y%m%d%H%M%S"),
                    "state": "open",
                }
            )
            self.message_post(body="(MODO DEMO) Se abrio declaracion exitosamente")
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
            "POST", "/declaracionJurada", env_type, "Abrir Declaracion", request_params
        )
        if error:
            return

        self.name = response.get("id")
        self.is_refund = response.get("rectificativa")
        if fechaCreacion := response.get("fechaCreacion"):
            self.open_date = datetime.fromisoformat(fechaCreacion[:26])
        if fechaVencimiento := response.get("fechaVencimiento"):
            self.due_date = datetime.fromisoformat(fechaVencimiento[:26])
        if fechaCierre := response.get("fechaCierre"):
            self.close_date = datetime.fromisoformat(fechaCierre[:26])
        self.state = "open"

        self.message_post(body="Declaracion fue abierta con exito")

    def action_update_status(self):
        """Consulta y actualiza el estado de la declaración jurada en ARBA en el Odoo

        Ejemplo de los datos del request
        {
            "cuitAgente": self.company_id.partner_id.ensure_vat(),
            "quincena": self._get_fortnight(self.date),
            "actividadId": 6,
            "anio": self.date.year,
            "mes": self.date.month,
        }

        Ejemplo del response
        [
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
        if env_type == "demo":
            # Simular que nos conectamos y hacemos la declaracion pero modo dummy local
            self.state = "open" if self.state != "open" else "close"
            self.message_post(body="(MODO DEMO) Fue actualizado el estado de la DJ")
            return
        response, error = self._process_arba_response(
            "GET",
            f"/declaracionJurada?cuitAgente={int(self.company_id.partner_id.ensure_vat())}&idDj={int(self.name)}",
            env_type,
            "Actualizar Declaración",
        )
        if error:
            return

        dj_state = response[0].get("estado")
        self.state = "open" if dj_state == "Abierto" else "close"
        self.message_post(body="Fue actualizado el estado de la DJ")
