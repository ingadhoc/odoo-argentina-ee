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

    def _get_journal_codes(self):
        self.ensure_one()

        # CAEA documents
        if 'CAEA' in self.l10n_ar_afip_pos_system:
            usual_codes = ['1', '2', '3', '6', '7', '8', '11', '12', '13']
            receipt_codes = ['4', '9', '15']
            receipt_m_code = ['54']
            invoice_m_code = ['51', '52', '53']
            mipyme_codes = ['201', '202', '203', '206', '207', '208', '211', '212', '213']
            return usual_codes + receipt_codes + invoice_m_code + receipt_m_code + mipyme_codes

        return super()._get_journal_codes()


