from odoo import api, fields, models, _


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    l10n_ar_contingency_journal_id = fields.Many2one(
        'account.journal', copy=False, string="Contingency Journal",
        domain="[('l10n_ar_afip_pos_system', 'in', ['II_IM', 'RAW_MAW_CAEA']), ('company_id', '=', company_id)]")

    def _get_l10n_ar_afip_pos_types_selection(self):
        """ Add more options to the selection field l10n_ar_afip_pos_system AFIP POS System """
        res = super()._get_l10n_ar_afip_pos_types_selection()
        res.append(('RAW_MAW_CAEA', _('CAEA - Electronic Invoice - Web Service')))
        return res

    @api.depends('l10n_ar_afip_pos_system')
    def _compute_l10n_ar_afip_ws(self):
        """ Depending on AFIP POS System selected set the proper AFIP WS """
        super()._compute_l10n_ar_afip_ws()
        self.filtered(lambda x: x.l10n_ar_afip_pos_system == 'RAW_MAW_CAEA').l10n_ar_afip_ws = 'wsfe'

    def _get_journal_codes(self):
        """ If CAEA journal then try to compute the same docs types as the related regular electronic journal """
        self.ensure_one()
        if self.l10n_ar_afip_pos_system and 'CAEA' in self.l10n_ar_afip_pos_system and self.type == 'sale':
            simil_ws = self._get_caea_simil_ws(self.l10n_ar_afip_pos_system)
            return self._get_codes_per_journal_type(simil_ws)
        return super()._get_journal_codes()

    @api.model
    def _get_caea_simil_ws(self, afip_ws):
        # Improve in next versions
        return afip_ws.replace('_CAEA', '').replace('_caea', '')
