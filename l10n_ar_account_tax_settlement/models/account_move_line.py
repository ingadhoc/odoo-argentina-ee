from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_settlement_tax(self, date=None):
        """Método puente para poder usar l10n_ar_tax_settlement_backward_comp
        Deprecar este método cuando se deprecie con l10n_ar_tax_settlement_backward_comp.
        El parámetro date es porque si la base no tiene instalado l10n_ar_tax_settlement_backward_comp
        entonces va a arrojar error si en alguna llamada al método se le pasa date.
        Ejemplo: método iibb_aplicado_agip_files_values de account_tax en módulo
        l10n_ar_account_tax_settlement hace la llamada tax = line._get_settlement_tax(date=date)"""
        self.ensure_one()
        return self.tax_line_id
