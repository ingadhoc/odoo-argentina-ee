import datetime

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def copy_data(self, default=None):
        """Duplicating creates the record right away (there is no edit step before saving),
        so a copied journal would always collide with the original's POS number. Assign the
        next POS number free among every POS journal of the company instead; the user must
        review it afterwards."""
        vals_list = super().copy_data(default=default)
        assigned = set()
        for journal, vals in zip(self, vals_list):
            if not journal.l10n_ar_is_pos or "l10n_ar_afip_pos_number" in (default or {}):
                continue
            used = (
                set(
                    self.search(
                        [
                            ("company_id", "=", vals.get("company_id", journal.company_id.id)),
                            ("l10n_ar_is_pos", "=", True),
                        ]
                    ).mapped("l10n_ar_afip_pos_number")
                )
                | assigned
            )
            vals["l10n_ar_afip_pos_number"] = next(n for n in range(1, 100000) if n not in used)
            assigned.add(vals["l10n_ar_afip_pos_number"])
        return vals_list

    @api.constrains("l10n_ar_afip_pos_number", "company_id")
    def _check_l10n_ar_afip_pos_number_unique(self):
        """Two sale journals sharing the ARCA POS number and POS system would share the same
        document numbering; on electronic journals ARCA rejects the documents (error 10016).
        Sharing the number between different POS systems stays allowed: native and OBA demo
        data legitimately do it, and so do databases migrated from pre-printed to electronic
        invoicing. Only plain columns trigger the check on purpose: recomputes of stored
        computed fields during installs and upgrades must not re-validate historical records."""
        for journal in self.filtered(lambda j: j.l10n_ar_is_pos and j.l10n_ar_afip_pos_number):
            duplicate = self.search(
                [
                    ("id", "!=", journal.id),
                    ("company_id", "=", journal.company_id.id),
                    ("l10n_ar_is_pos", "=", True),
                    ("l10n_ar_afip_pos_number", "=", journal.l10n_ar_afip_pos_number),
                    ("l10n_ar_afip_pos_system", "=", journal.l10n_ar_afip_pos_system),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _(
                        'The ARCA POS number %(pos_number)s is already used by the journal "%(journal)s", '
                        "which has the same POS system. Two sale journals cannot share the POS number and "
                        "POS system because they would share the document numbering.",
                        pos_number=journal.l10n_ar_afip_pos_number,
                        journal=duplicate.display_name,
                    )
                )

    def l10n_ar_check_afip_doc_types(self):
        """This method shows the valid document types for each Webservice."""
        self.ensure_one()
        connection = self.company_id._l10n_ar_get_connection(self.l10n_ar_afip_ws)
        client, auth = connection._get_client()
        if self.l10n_ar_afip_ws == "wsfe":
            response = client.service.FEParamGetTiposCbte(auth)
        elif self.l10n_ar_afip_ws == "wsfex":
            response = client.service.FEXGetPARAM_Cbte_Tipo(auth)
        elif self.l10n_ar_afip_ws == "wsbfe":
            response = client.service.BFEGetPARAM_Tipo_Cbte(auth)
        else:
            raise UserError(_('"Get Document Types" is not implemented for webservice %s') % self.l10n_ar_afip_ws)

        msg = self._format_afip_doc_types(self.l10n_ar_afip_ws, response)
        msg = _("Authorized Document Clases on ARCA:\n%s") % msg
        raise UserError(msg)

    def _format_afip_doc_types(self, ws, response):
        """Given the response and the Webservice used, returns a more legible message to be shown to the users."""
        events = False
        if ws == "wsfe":
            if response["Errors"]:
                raise UserError(response["Errors"])
            elif response["Events"]:
                events = str(response["Events"])
            result_key = "ResultGet"
            voucher_key = "CbteTipo"
            id_key = "Id"
            name_key = "Desc"
            date_from_key = "FchDesde"
            date_to_key = "FchHasta"
        elif ws == "wsfex" or ws == "wsbfe":
            error_key = "FEXErr" if ws == "wsfex" else "BFEErr"
            events_key = "FEXEvents" if ws == "wsfex" else "BFEEvents"
            if response[error_key]["ErrMsg"] != "OK":
                raise UserError(response[error_key]["ErrMsg"])
            elif response[events_key]["EventMsg"] != "Ok":
                events = str(response[events_key]["EventMsg"])
            result_key = "FEXResultGet" if ws == "wsfex" else "BFEResultGet"
            voucher_key = "ClsFEXResponse_Cbte_Tipo" if ws == "wsfex" else "ClsBFEResponse_Tipo_Cbte"
            id_key = "Cbte_Id"
            name_key = "Cbte_Ds"
            date_from_key = "Cbte_vig_desde"
            date_to_key = "Cbte_vig_hasta"

        msg = ""
        for document in response[result_key][voucher_key]:
            date_from = format_date(
                self.env, datetime.datetime.strptime(document[date_from_key], "%Y%m%d"), date_format="dd/MM/Y"
            )
            line = " - [" + str(document[id_key]) + "] " + document[name_key] + _(" Vigente desde: ") + date_from
            if document[date_to_key] != "NULL":
                date_to = format_date(
                    self.env, datetime.datetime.strptime(document[date_to_key], "%Y%m%d"), date_format="dd/MM/Y"
                )
                line += _(" hasta: ") + date_to
            msg += line + "\n"
        if events:
            msg += _("\n\nAdicionalmente, ARCA devuelve este evento: ") + events
        return msg
