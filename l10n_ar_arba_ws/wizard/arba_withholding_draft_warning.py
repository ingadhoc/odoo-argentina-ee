# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ArbaWithholdingDraftWarning(models.TransientModel):
    _name = "arba.withholding.draft.warning"
    _description = "ARBA Withholding Draft Warning"

    payment_id = fields.Many2one("account.payment", required=True)
    withholding_count = fields.Integer(readonly=True)
    withholding_info = fields.Html(readonly=True)

    def action_confirm_reset_to_draft(self):
        """Confirma que el usuario entiende que la retención quedará informada en ARBA
        y procede a volver el pago a borrador."""
        self.ensure_one()
        # Volver el pago a borrador (las retenciones con certificado no se reenviarán)
        self.payment_id.with_context(skip_arba_draft_warning=True).action_draft()
        return {"type": "ir.actions.act_window_close"}
