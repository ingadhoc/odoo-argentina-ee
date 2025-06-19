from odoo import _, fields, models
from odoo.exceptions import RedirectWarning


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_settlement_tax(self, date=None):
        # is_backward_tax lo usamos para partner aliquot
        if not self.tax_line_id.is_backward_tax:
            # si tiene vinculada retencion y la misma tiene regime_tax_id es una retencion de ganancias migrada
            # devolvemos ese impuesto, si no, devolvemos el impuesto de la linea
            return self.withholding_id.regime_tax_id or self.tax_line_id
        is_perception = self.move_id.is_invoice()
        partner_field = (
            self.partner_id.l10n_ar_partner_perception_ids if is_perception else self.partner_id.l10n_ar_partner_tax_ids
        )
        date = date or self.date
        if partner_tax := partner_field.filtered(
            lambda x: x.company_id == self.company_id
            and x.tax_id.l10n_ar_state_id == self.tax_line_id.l10n_ar_state_id
            and (x.from_date <= date if x.from_date else not x.from_date)
            and (x.to_date >= date if x.to_date else not x.from_date)
        ):
            return partner_tax.tax_id
        tax_type_str = "sale perception" if is_perception else "purchase withholding"
        raise RedirectWarning(
            message=_(
                "The partner '%(partner_name)s' does not have '%(state_name)s %(tax_type_str)s' tax set for date %(line_date)s. [Journal entry: %(journal_entry_name)s]",
                partner_name=self.partner_id.name,
                tax_type_str=tax_type_str,
                journal_entry_name=self.move_id.name,
                state_name=self.tax_line_id.l10n_ar_state_id.name,
                line_date=fields.Date.to_string(date),
            ),
            action={
                "type": "ir.actions.act_window",
                "res_model": "res.partner",
                "views": [(False, "form")],
                "res_id": self.partner_id.id,
                "name": _("Partner"),
                "view_mode": "form",
            },
            button_text=_("Edit Partner"),
        )
