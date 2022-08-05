from odoo import models, fields


class ResCompany(models.Model):

    _inherit = 'res.company'

    l10n_ar_use_caea = fields.Boolean(compute="compute_l10n_ar_use_caea", store=True)

    l10n_ar_contingency_mode = fields.Boolean('Contingency Mode')

    l10n_ar_last_contigency = fields.Datetime('Last Contigency Activated', readonly="1")

    def write(self, values):
        if values.get('l10n_ar_contingency_mode') == True:
            values.update({'l10n_ar_last_contigency': fields.Datetime.now()})
        return super().write(values)

    def compute_l10n_ar_use_caea(self):
        """ Boolean used to know if we need CAEA number sincronization each fornight"""
        caea_companies = self.env['account.journal'].search([('l10n_ar_afip_pos_system', '=', 'RAW_MAW_CAEA')]).mapped('company_id')
        caea_companies.l10n_ar_use_caea = True
        (self - caea_companies).l10n_ar_use_caea = False

    def _l10n_ar_get_connection(self, afip_ws):
        """ Get simil ws for caea """
        self.ensure_one()
        if 'caea' in afip_ws:
            afip_ws = self.env['account.journal']._get_caea_simil_ws(afip_ws)
        return super()._l10n_ar_get_connection(afip_ws=afip_ws)

    def cron_exit_contigency_mode(self):
        self.search([
            ('l10n_ar_contingency_mode', '=', True),
            ('l10n_ar_last_contigency', '<', fields.Datetime.subtract(
                fields.Datetime.now(), hours=1))]).l10n_ar_contingency_mode = False
