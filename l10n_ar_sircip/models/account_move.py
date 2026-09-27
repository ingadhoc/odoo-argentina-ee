##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ar_sircip_context(self):
        """SIRCIP depends on the delivery province, which l10n_ar_tax does not pass along."""
        self.ensure_one()
        return self.with_context(l10n_ar_delivery_partner_id=self.partner_shipping_id.id)

    def _l10n_ar_recompute_fiscal_position_taxes(self):
        # EXTEND l10n_ar_tax
        for move in self:
            super(AccountMove, move._l10n_ar_sircip_context())._l10n_ar_recompute_fiscal_position_taxes()

    @api.onchange("partner_shipping_id")
    def _onchange_l10n_ar_sircip_partner_shipping(self):
        self._l10n_ar_recompute_fiscal_position_taxes()

    def action_post(self):
        for move in self.filtered(lambda x: x.move_type == "out_invoice" and x.fiscal_position_id):
            move.fiscal_position_id.with_context(
                l10n_ar_delivery_partner_id=move.partner_shipping_id.id
            )._l10n_ar_check_perceptions(move.partner_id, move.invoice_date or fields.Date.context_today(move))
        return super().action_post()

    def write(self, vals):
        res = super().write(vals)
        # Like l10n_ar_tax does with the date: recompute perceptions when the delivery changes from code
        if "partner_shipping_id" in vals and "invoice_line_ids" not in vals:
            self._l10n_ar_recompute_fiscal_position_taxes()
        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_computed_taxes(self):
        # EXTEND l10n_ar_tax
        line = self.with_context(l10n_ar_delivery_partner_id=self.move_id.partner_shipping_id.id)
        return super(AccountMoveLine, line)._get_computed_taxes()
