from . import models
from odoo.addons.l10n_ar_edi.models.account_move import AccountMove

def monkey_patches():

    # Revertimos este cambio de odoo para que los clientes puedan pasar a borrador las facturas confirmadas en afip
    # https://github.com/odoo/enterprise/pull/63407/files#diff-2459e118c605cf039bb94c62561285ad753b6a27c571f10a25547ee9b01aa318R76-R84

    original_method = AccountMove._compute_show_reset_to_draft_button
    # monkey patch
    def _compute_show_reset_to_draft_button(self):
        original_method(self)
        for move in self:
            move.show_reset_to_draft_button = not move.restrict_mode_hash_table and move.state in ('posted', 'cancel')

    AccountMove._compute_show_reset_to_draft_button = _compute_show_reset_to_draft_button
