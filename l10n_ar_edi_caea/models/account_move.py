from odoo import models, fields


class AccountMove(models.Model):

    _inherit = 'account.move'

    l10n_ar_caea_id = fields.Many2one('l10n.ar.caea', copy=False)
    l10n_ar_afip_result = fields.Selection(selection_add=[('R', 'Rejected in AFIP')])
