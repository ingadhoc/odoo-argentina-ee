from odoo import api, models, _


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    def _get_l10n_ar_afip_pos_types_selection(self):
        """ Add more options to the selection field l10n_ar_afip_pos_system AFIP POS System """
        res = super()._get_l10n_ar_afip_pos_types_selection()
        res.append(('RAW_MAW_CAEA', _('CAEA - Electronic Invoice - Web Service')))
        return res

    def _get_l10n_ar_afip_ws(self):
        res = super()._get_l10n_ar_afip_ws()
        res.append(('wsfe_caea', _('CAEA - Electronic Invoice (WSFEv1)')))
        return res

    @api.depends('l10n_ar_afip_pos_system')
    def _compute_l10n_ar_afip_ws(self):
        """ Depending on AFIP POS System selected set the proper AFIP WS """
        super()._compute_l10n_ar_afip_ws()
        self.filtered(lambda x: x.l10n_ar_afip_pos_system == 'RAW_MAW_CAEA').l10n_ar_afip_ws = 'wsfe_caea'
