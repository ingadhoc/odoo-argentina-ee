# -*- coding: utf-8 -*-
from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # TODO: sin esto sale un error al guardar un nuevo cliente. Revisar.
    @api.constrains('vat', 'l10n_latam_identification_type_id')
    def check_vat(self):
        type_id = int(self.l10n_latam_identification_type_id.id)
        l10n_ar_partners = self.filtered(lambda self: self.env['l10n_latam.identification.type'].browse(type_id).l10n_ar_afip_code)
        l10n_ar_partners.l10n_ar_identification_validation()
        return super(ResPartner, self - l10n_ar_partners).check_vat()

