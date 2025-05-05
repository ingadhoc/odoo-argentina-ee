from odoo import _, fields, models
from odoo.exceptions import RedirectWarning


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_settlement_tax(self):
        """Este método retorna el impuesto del apunte contable, pero si dicho impuesto está archivado porque el apunte contable +viene de la versión anterior (lo archivamos en ul 1538) entonces tenemos que retornar el impuesto nuevo que corresponde a la versión 18, si no se encuentra dicho impuesto entonces devolvemos RedirectWarning. TODO: deprecar en el futuro cuando no se generen más txt de apuntes contables que vengan de versión anterior a la 18 (es decir, solo dejar 'return self.tax_line_id', también corregir los lugares donde se llame a este método)."""
        self.ensure_one()
        if not self.tax_line_id.active:
            is_perception = self.move_id.is_invoice()
            partner_field = (
                self.partner_id.l10n_ar_partner_perception_ids
                if is_perception
                else self.partner_id.l10n_ar_partner_tax_ids
            )
            if partner_tax := partner_field.filtered(
                lambda x: x.company_id == self.company_id
                and x.tax_id.l10n_ar_state_id == self.tax_line_id.l10n_ar_state_id
                and (x.from_date <= self.date if x.from_date else not x.from_date)
                and (x.to_date >= self.date if x.to_date else not x.from_date)
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
                    line_date=fields.Date.to_string(self.date),
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
        return self.tax_line_id
