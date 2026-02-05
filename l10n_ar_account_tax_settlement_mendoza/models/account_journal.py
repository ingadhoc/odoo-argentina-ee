from odoo import _, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def iibb_aplicado_sircar_files_values(self, move_lines):
        """Extendemos este método del original de l10n_ar_account_tax_settlement para mendoza. El objetivo de este método es validar que el impuesto de mendoza tenga código de régimen."""
        mendoza_state = self.env.ref("base.state_ar_m")
        if missing_codigo_regimen_mendoza_taxes := move_lines.filtered(
            lambda x: x.payment_id
            and x.tax_line_id.l10n_ar_state_id == mendoza_state
            and not x.tax_line_id.l10n_ar_code
        ).mapped("tax_line_id"):
            tax_lines = []
            for mdza_tax in missing_codigo_regimen_mendoza_taxes:
                tax_lines.append(_("ID: %(id)s\t\t- Name: %(name)s", id=mdza_tax.id, name=mdza_tax.display_name))
            details = _(
                "Los siguientes impuestos de Mendoza no tienen código de régimen (campo 'Código AFIP' l10n_ar_code):\n\n%(taxes)s",
                taxes="\n".join(tax_lines),
            )
            raise UserError(details)
        return super().iibb_aplicado_sircar_files_values(move_lines)
