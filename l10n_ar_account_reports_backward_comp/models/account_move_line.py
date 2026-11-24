from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_settlement_tax(self, date=None):
        # is_backward_tax lo usamos para partner aliquot
        if not self.tax_line_id.is_backward_tax:
            # si tiene vinculada retencion y la misma tiene regime_tax_id es una retencion de ganancias migrada
            # devolvemos ese impuesto, si no, devolvemos el impuesto de la linea
            return self.withholding_id.regime_tax_id or self.tax_line_id
        if self.tax_line_id.active:
            # Si el impuesto del apunte está activo entonces no fue migrado (el apunte fue creado en la nueva versión)
            # por lo tanto devolvemos el impuesto del apunte y no lo buscamos en el contacto
            return self.tax_line_id
        is_perception = self.move_id.is_invoice()
        partner_field = (
            self.partner_id.l10n_ar_partner_perception_ids if is_perception else self.partner_id.l10n_ar_partner_tax_ids
        )
        date = date or self.date
        earnings_types = ["earnings", "earnings_scale"]
        is_earnings = self.tax_line_id.l10n_ar_tax_type in earnings_types
        regime_code = self.withholding_id.regime_code
        if regime_code and is_earnings:
            # migrated earnings withholding: the regime stored on the withholding is the one that was applied,
            # so it wins over the partner aliquot (the regime the partner has today)
            # (not regime_tax_id, which is reset if the payment entry is rebuilt)
            if regime_tax := self.env["account.tax"].search(
                [
                    *self.env["account.tax"]._check_company_domain(self.company_id),
                    ("l10n_ar_code", "=", regime_code),
                    ("l10n_ar_tax_type", "in", earnings_types),
                    ("l10n_ar_withholding_payment_type", "=", "supplier"),
                ],
                limit=1,
            ):
                return regime_tax
        if self.tax_line_id.l10n_ar_tax_type == "earnings":
            if partner_tax := partner_field.filtered(
                lambda x: x.company_id == self.company_id
                and not x.tax_id.l10n_ar_state_id
                and x.tax_id.l10n_ar_tax_type in ["earnings", "earnings_scale"]
                and (x.from_date <= date if x.from_date else True)
                and (x.to_date >= date if x.to_date else True)
            ):
                return partner_tax.tax_id
        if partner_tax := partner_field.filtered(
            lambda x: x.company_id == self.company_id
            and x.tax_id.l10n_ar_state_id == self.tax_line_id.l10n_ar_state_id
            # earnings taxes have no state, so other national aliquots (VAT, SUSS) would match too
            and (not is_earnings or x.tax_id.l10n_ar_tax_type in earnings_types)
            and (x.from_date <= date if x.from_date else not x.from_date)
            and (x.to_date >= date if x.to_date else not x.to_date)
        ):
            return partner_tax.tax_id
        return self.tax_line_id
