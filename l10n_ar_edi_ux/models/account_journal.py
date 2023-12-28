from odoo import models, fields, _, api
from odoo.exceptions import UserError
from odoo.tools import format_date
import datetime


class AccountJournal(models.Model):
    _inherit = "account.journal"

    check_add_debit_button = fields.Boolean(
        string="Agregar botón de débito",
        help="Si marca esta opción podrá debitar los cheques con un botón desde los mismo.")
    check_debit_journal_id = fields.Many2one('account.journal', compute='_compute_check_debit_journal', store=True, readonly=False, domain="[('company_id', '=', company_id), ('type', '=', 'general')]", help="Debe seleccionar un diario de tipo 'Varios' donde se realizará el asiento del débito")

    def l10n_ar_check_afip_doc_types(self):
        """ This method shows the valid document types for each Webservice. """
        self.ensure_one()
        connection = self.company_id._l10n_ar_get_connection(self.l10n_ar_afip_ws)
        client, auth = connection._get_client()
        if self.l10n_ar_afip_ws == 'wsfe':
            response = client.service.FEParamGetTiposCbte(auth)
        elif self.l10n_ar_afip_ws == 'wsfex':
            response = client.service.FEXGetPARAM_Cbte_Tipo(auth)
        elif self.l10n_ar_afip_ws == 'wsbfe':
            response = client.service.BFEGetPARAM_Tipo_Cbte(auth)
        else:
            raise UserError(_('"Get Document Types" is not implemented for webservice %s') % self.l10n_ar_afip_ws)

        msg = self._format_afip_doc_types(self.l10n_ar_afip_ws, response)
        msg = (_("Authorized Document Clases on AFIP:\n%s" % msg))
        raise UserError(msg)

    def _format_afip_doc_types(self, ws, response):
        """ Given the response and the Webservice used, returns a more legible message to be shown to the users. """
        if ws == 'wsfe':
            if response['Errors']:
                raise UserError(response['Errors'])
            elif response['Events']:
                raise UserError(response['Events'])
            result_key = 'ResultGet'
            voucher_key = 'CbteTipo'
            id_key = 'Id'
            name_key = 'Desc'
            date_from_key = 'FchDesde'
            date_to_key = 'FchHasta'
        elif ws == 'wsfex' or ws == 'wsbfe':
            error_key = 'FEXErr' if ws == 'wsfex' else 'BFEErr'
            events_key = 'FEXEvents' if ws == 'wsfex' else 'BFEEvents'
            if response[error_key]['ErrMsg'] != 'OK':
                raise UserError(response[error_key]['ErrMsg'])
            elif response[events_key]['EventMsg'] != 'Ok':
                raise UserError(response[events_key]['EventMsg'])

            result_key = 'FEXResultGet' if ws == 'wsfex' else 'BFEResultGet'
            voucher_key = 'ClsFEXResponse_Cbte_Tipo' if ws == 'wsfex' else 'ClsBFEResponse_Tipo_Cbte'
            id_key = 'Cbte_Id'
            name_key = 'Cbte_Ds'
            date_from_key = 'Cbte_vig_desde'
            date_to_key = 'Cbte_vig_hasta'

        msg = ""
        for document in response[result_key][voucher_key]:
            date_from = format_date(self.env, datetime.datetime.strptime(document[date_from_key], '%Y%m%d'), date_format='dd/MM/Y')
            line = " - [" + str(document[id_key]) + "] " + document[name_key] + " Vigente desde: " + date_from
            if document[date_to_key] != 'NULL':
                date_to = format_date(self.env, datetime.datetime.strptime(document[date_to_key], '%Y%m%d'), date_format='dd/MM/Y')
                line += " hasta: " + date_to
            msg += line + "\n"
        return msg

    @api.depends('check_add_debit_button')
    def _compute_check_debit_journal(self):
        """ En caso de que el campo 'Agregar botón de débito' (check_debit_journal_id) sea 'False' entonces debemos asegurarnos que el campo check_debit_journal_id esté vacío para evitar inconvenientes en caso de necesitar debitar un cheque. """
        for journal in self.filtered(lambda x: not x.check_add_debit_button):
            journal.check_debit_journal_id = False
