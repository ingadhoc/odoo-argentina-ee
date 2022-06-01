from odoo import models, _


class ValidateAccountMove(models.TransientModel):

    _inherit = "validate.account.move"

    def filter_posted_moves(self, moves):
        """ Extend to only considered posted method the ones that has been properly
        validated in AFIP """
        res = super().filter_posted_moves(moves)
        electronic_not_validated_in_afip = res.filtered(
            lambda x: x.l10n_ar_afip_ws and x.l10n_ar_afip_result not in ['A', 'O'])
        return res - electronic_not_validated_in_afip
