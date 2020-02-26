from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def update_partner_data_from_afip(self):
        """ Funcion que llama al wizard para actualizar data de partners desde afip sin abrir wizard.
        Podríamos mejorar  pasando un argumento para sobreescribir o no valores que esten o no definidos
        Podriamos mejorarlo moviento lógica del wizard a esta funcion y que el wizard use este método. """
        for rec in self:
            wiz = rec.env['res.partner.update.from.padron.wizard'].with_context(
                active_ids=rec.ids, active_model=rec._name).create({})
            wiz.change_partner()
            wiz.update_selection()

    @api.model
    def try_write_commercial(self, data):
        """ User for website. capture the validation errors and return them.
        return (error, error_message) = (dict[fields], list(str())) """
        error = dict()
        error_message = []
        vat = data.get('vat')
        l10n_latam_identification_type_id = data.get('l10n_latam_identification_type_id')
        l10n_ar_afip_responsibility_type_id = data.get('l10n_ar_afip_responsibility_type_id', False)

        if vat and l10n_latam_identification_type_id:
            commercial_partner = self.env['res.partner'].sudo().browse(int(data.get('commercial_partner_id')))
            try:
                values = {
                    'vat': vat,
                    'l10n_latam_identification_type_id': int(l10n_latam_identification_type_id),
                    'l10n_ar_afip_responsibility_type_id':
                        int(l10n_ar_afip_responsibility_type_id) if l10n_ar_afip_responsibility_type_id else False}
                commercial_fields = ['vat', 'l10n_latam_identification_type_id', 'l10n_ar_afip_responsibility_type_id']
                values = commercial_partner.remove_readonly_required_fields(commercial_fields, values)
                with self.env.cr.savepoint():
                    commercial_partner.write(values)
            except Exception as exception_error:
                _logger.error(exception_error)
                error['vat'] = 'error'
                error['l10n_latam_identification_type_id'] = 'error'
                error_message.append(_(exception_error))
        return error, error_message

    def remove_readonly_required_fields(self, required_fields, values):
        """ In some cases we have information showed to the user in the for that is required but that is already set
        and readonly. We do not really update this fields and then here we are trying to write them: the problem is
        that this fields has a constraint if we are trying to re-write them (even when is the same value).

        This method remove this (field, values) for the values to write in order to do avoid the constraint and not
        re-writted again when they has been already writted.

        param: @required_fields: (list) fields of the fields that we want to check
        param: @values (dict) the values of the web form

        return: the same values to write and they do not include required/readonly fields.
        """
        self.ensure_one()
        for r_field in required_fields:
            value = values.get(r_field)
            if r_field.endswith('_id'):
                if self[r_field].id == value:
                    values.pop(r_field, False)
            else:
                if self[r_field] == value:
                    values.pop(r_field, False)
        return values
