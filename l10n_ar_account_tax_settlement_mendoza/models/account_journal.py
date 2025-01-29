from odoo import models, _
from odoo.exceptions import RedirectWarning


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def iibb_aplicado_sircar_files_values(self, move_lines):
        """ Extendemos este método del original de l10n_ar_account_tax_settlement para mendoza. El objetivo de este método es validar que el impuesto de mendoza tenga código de régimen.
        """
        tax_group_id_mendoza_id = self.env.ref('l10n_ar_ux.tax_group_retencion_iibb_za')
        mendoza_lines = move_lines.filtered(lambda x: x.payment_id and x.tax_line_id.withholding_type == 'code' and x.tax_group_id == tax_group_id_mendoza_id)
        missing_codigo_regimen = mendoza_lines.filtered(lambda x: not x.payment_id.tax_withholding_id.codigo_regimen)
        if mendoza_lines and missing_codigo_regimen:
            raise RedirectWarning(
                message=_("El impuesto '%s' not tiene código de regimen en solapa 'Opciones avanzadas' campo 'Codigo de regimen IVA'.", missing_codigo_regimen.payment_id.tax_withholding_id.name),
                action={
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.tax',
                    'views': [(False, 'form')],
                    'res_id': mendoza_lines.tax_line_id.id,
                    'name': _('Tax'),
                    'view_mode': 'form',
                },
                button_text=_('Editar Impuesto'),
            )
        return super().iibb_aplicado_sircar_files_values(move_lines)
