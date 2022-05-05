from odoo import models, fields


class ResCompany(models.Model):

    _inherit = 'res.company'

    l10n_ar_use_caea = fields.Boolean(compute="compute_l10n_ar_use_caea")

    def compute_l10n_ar_use_caea(self):
        """ Boolean used to know if we need CAEA number sincronization each fornight"""
        caea_companies = self.env['account.jounral'].search([('l10n_ar_afip_pos_system', '=', 'RAW_MAW_CAEA')]).mapped('company_id')
        caea_companies.l10n_ar_use_caea = True
        (self - caea_companies).l10n_ar_use_caea = False
