from odoo import _, api, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _get_l10n_ar_afip_ws(self):
        """Return the list of values of the selection field."""
        res = super()._get_l10n_ar_afip_ws()
        return res + [
            ("wsmtxca", _("Codificación de producto - RG2904 (WSMTXCA)")),
        ]

    def _get_l10n_ar_afip_pos_types_selection(self):
        """Add more options to the selection field AFIP POS System, re order options by common use"""
        res = super()._get_l10n_ar_afip_pos_types_selection()
        res.append(("WSMTXCAWS", _("Codificación de producto - Web Service")))
        return res

    @api.depends("l10n_ar_afip_pos_system")
    def _compute_l10n_ar_afip_ws(self):
        """Depending on AFIP POS System selected set the proper AFIP WS"""
        super()._compute_l10n_ar_afip_ws()
        for rec in self:
            if rec.l10n_ar_afip_pos_system == "WSMTXCAWS":
                rec.l10n_ar_afip_ws = "wsmtxca"

    def l10n_ar_check_afip_pos_number(self):
        """Return information about the AFIP POS numbers related to the given AFIP WS"""
        if self.l10n_ar_afip_ws != "wsmtxca":
            return super().l10n_ar_check_afip_pos_number()
        self.ensure_one()
        connection = self.company_id._l10n_ar_get_connection(self.l10n_ar_afip_ws)
        client, auth = connection._get_client()
        if self.company_id._get_environment_type() == "testing":
            raise UserError(
                _(
                    '"Check Available AFIP PoS" is not implemented in testing mode for webservice %s',
                    self.l10n_ar_afip_ws,
                )
            )
        auth = self._wsmtxca_convert_auth(auth)
        response = client.service.consultarPuntosVentaCAE(auth)
        raise UserError(response)

    def _l10n_ar_get_afip_last_invoice_number(self, document_type):
        """Consult via webservice the number of the last invoice register"""
        afip_ws = self.l10n_ar_afip_ws
        if afip_ws != "wsmtxca":
            return super()._l10n_ar_get_afip_last_invoice_number(document_type)
        self.ensure_one()
        if self.env.registry.in_test_mode():
            return 0

        pos_number = self.l10n_ar_afip_pos_number
        connection = self.company_id._l10n_ar_get_connection(afip_ws)
        client, auth = connection._get_client()
        last = errors = False

        data = self._wsmtxca_convert_auth(auth)
        response = client.service.consultarUltimoComprobanteAutorizado(
            data,
            consultaUltimoComprobanteAutorizadoRequest={
                "codigoTipoComprobante": document_type.code,
                "numeroPuntoVenta": pos_number,
            },
        )
        if response.numeroComprobante:
            last = response.numeroComprobante
        if response.arrayErrores:
            errors = "".join(
                ["\n* Code %s: %s" % (err.codigo, err.descripcion) for err in response.arrayErrores.codigoDescripcion]
            )
            error_first_invoice = [1502]
            if error_first_invoice == [err.codigo for err in response.arrayErrores.codigoDescripcion]:
                errors = False  # No invoices found for this document type
                last = 0

        if errors:
            raise UserError(_("We received this error while consulting the last invoice number from ARCA:\n%s", errors))
        return last

    @api.model
    def _get_codes_per_journal_type(self, afip_pos_system):
        res = super()._get_codes_per_journal_type(afip_pos_system)
        if afip_pos_system != "WSMTXCAWS":
            return res

        usual_codes = ["1", "2", "3", "6", "7", "8"]
        invoice_m_code = ["51", "52", "53"]
        mipyme_codes = ["201", "202", "203", "206", "207", "208"]
        codes = usual_codes + invoice_m_code + mipyme_codes

        res[0] = ("code", "in", codes)
        return res

    @api.model
    def _wsmtxca_convert_auth(self, auth):
        res = {"sign": auth.get("Sign"), "token": auth.get("Token"), "cuitRepresentada": auth.get("Cuit")}
        return res

    def l10n_ar_check_afip_doc_types(self):
        """This method shows the valid document types for each Webservice."""
        self.ensure_one()
        if self.l10n_ar_afip_ws != "wsmtxca":
            return super().l10n_ar_check_afip_doc_types()

        connection = self.company_id._l10n_ar_get_connection(self.l10n_ar_afip_ws)
        client, auth = connection._get_client()
        auth = self._wsmtxca_convert_auth(auth)
        response = client.service.consultarTiposComprobante(auth)
        msg = self._format_afip_doc_types(self.l10n_ar_afip_ws, response)
        msg = _("Tipos de Documentos Autorizados en ARCA:\n%s") % msg
        raise UserError(msg)

    def _format_afip_doc_types(self, ws, response):
        """Given the response and the Webservice used, returns a more legible message to be shown to the users."""
        if ws != "wsmtxca":
            return super()._format_afip_doc_types(ws, response)

        events = False
        if response["evento"]:
            events = str(["%s: %s" % (evt.codigo, evt.descripcion) for evt in response["evento"]])
        msg = ""
        for document in response["arrayTiposComprobante"]["codigoDescripcion"]:
            msg += " - [" + str(document["codigo"]) + "] " + document["descripcion"] + "\n"
        if events:
            msg += "\n\nAdicional, ARCA devuelve este evento: " + events
        return msg
