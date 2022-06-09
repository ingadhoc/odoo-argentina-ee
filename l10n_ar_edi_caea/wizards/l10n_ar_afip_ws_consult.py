# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class L10nArAfipWsConsult(models.TransientModel):

    _inherit = 'l10n_ar_afip.ws.consult'

    journal_id = fields.Many2one(domain="[('l10n_ar_afip_pos_system', 'in', ['RAW_MAW', 'RAW_MAW_CAEA', 'BFEWS', 'FEEWS', ])]")
