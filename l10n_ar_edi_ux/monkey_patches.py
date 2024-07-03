from odoo.addons.l10n_ar_edi.models.account_move import AccountMove

original_method = AccountMove._compute_show_reset_to_draft_button


def monkey_patches():

    def _compute_show_reset_to_draft_button(self):
        """ Necesario debido este cambio https://github.com/odoo/enterprise/pull/63407/files#diff-2459e118c605cf039bb94c62561285ad753b6a27c571f10a25547ee9b01aa318R76-R84

        Este este monkey patch anulamos el metodo _compute_show_reset_to_draft_button que esta en el modulo l10n_ar
        para poder pasar a borrador facturas ya publicadas y validadas en AFIP (esto por si ocurre algun error en la
        factura ejemplo problemas de secuencias puedan corregir la factura), y lograr hacer esto permitiendo que
        funcione tambien para otros modulos """
        super(AccountMove, self)._compute_show_reset_to_draft_button()

    AccountMove._compute_show_reset_to_draft_button = _compute_show_reset_to_draft_button
