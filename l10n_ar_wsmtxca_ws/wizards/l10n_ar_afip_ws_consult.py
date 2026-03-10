import logging

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.zeep.helpers import serialize_object

_logger = logging.getLogger(__name__)


class L10nArAfipWsConsult(models.TransientModel):
    _inherit = "l10n_ar_afip.ws.consult"

    journal_id = fields.Many2one(
        domain="[('l10n_ar_afip_pos_system', 'in', ['RAW_MAW', 'BFEWS', 'FEEWS', 'WSMTXCAWS'])]",
    )

    def button_confirm(self):
        self.ensure_one()
        afip_ws = self.journal_id.l10n_ar_afip_ws

        # Si no es wsmtxca, delegar al método padre
        if afip_ws != "wsmtxca":
            return super().button_confirm()

        # Lógica específica para wsmtxca
        pos_number = self.journal_id.l10n_ar_afip_pos_number
        extra = []
        error = None

        if not afip_ws:
            raise UserError(_("No AFIP WS selected on point of sale %s", self.journal_id.name))
        if not self.number:
            raise UserError(_("Please set the number you want to consult"))

        connection = self.journal_id.company_id._l10n_ar_get_connection(afip_ws)
        client, auth = connection._get_client()

        auth = self.journal_id._wsmtxca_convert_auth(auth)
        response = client.service.consultarComprobante(
            auth,
            {
                "codigoTipoComprobante": self.document_type_id.code,
                "numeroPuntoVenta": pos_number,
                "numeroComprobante": self.number,
            },
        )

        if response.arrayErrores:
            error = "".join(
                [
                    _("\n* Code %s: %s", item.codigo, item.descripcion)
                    for item in response.arrayErrores.codigoDescripcion
                ]
            )
        if response.arrayObservaciones:
            extra += [
                _("\n* Observations %s: %s", item.codigo, item.descripcion)
                for item in response.arrayObservaciones.codigoDescripcion
            ]
        if response.evento:
            extra += [_("\n* Evento %s: %s", response.evento.codigo, response.evento.descripcion)]
        res = response.comprobante

        title = _("Invoice number %s\n", self.number)
        if error:
            _logger.warning("%s\n%s" % (title, error))
            raise UserError(_("AFIP Errors: %(error)s", error=error))

        msg = ""
        data = serialize_object(res, dict)
        for key, value in data.items():
            msg += " * %s: %s\n" % (key, value or "")
        if extra:
            msg += _("\nAdditional Information:\n") + "".join(extra)
        raise UserError(title + msg)
