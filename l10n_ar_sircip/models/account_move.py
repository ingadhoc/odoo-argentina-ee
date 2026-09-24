##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ar_sircip_context(self):
        """La percepción SIRCIP depende de la provincia de entrega, que l10n_ar_tax no transmite."""
        self.ensure_one()
        return self.with_context(l10n_ar_sircip_delivery_partner_id=self.partner_shipping_id.id)

    def _l10n_ar_recompute_fiscal_position_taxes(self):
        # EXTEND l10n_ar_tax
        for move in self:
            super(AccountMove, move._l10n_ar_sircip_context())._l10n_ar_recompute_fiscal_position_taxes()

    @api.onchange("partner_shipping_id")
    def _onchange_l10n_ar_sircip_partner_shipping(self):
        self._l10n_ar_recompute_fiscal_position_taxes()

    def write(self, vals):
        res = super().write(vals)
        # Igual que l10n_ar_tax con la fecha: si cambia la entrega desde código, recalculamos las percepciones.
        if "partner_shipping_id" in vals and "invoice_line_ids" not in vals:
            self._l10n_ar_recompute_fiscal_position_taxes()
        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_computed_taxes(self):
        # EXTEND l10n_ar_tax
        line = self.with_context(l10n_ar_sircip_delivery_partner_id=self.move_id.partner_shipping_id.id)
        return super(AccountMoveLine, line)._get_computed_taxes()
