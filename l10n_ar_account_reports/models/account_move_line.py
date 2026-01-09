from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_settlement_tax(self, date=None):
        """Método puente para poder usar l10n_ar_account_reports_backward_comp
        Deprecar este método cuando se deprecie con l10n_ar_account_reports_backward_comp.
        El parámetro date es porque si la base no tiene instalado l10n_ar_account_reports_backward_comp
        entonces va a arrojar error si en alguna llamada al método se le pasa date.
        Ejemplo: método iibb_aplicado_agip_files_values de account_tax en módulo
        l10n_ar_account_tax_settlement hace la llamada tax = line._get_settlement_tax(date=date)"""
        self.ensure_one()
        return self.tax_line_id

    def _affect_tax_report(self):
        """En argentina estamos haciendo que el asiento de liquidación de IVA pueda ser modificado por el usuario
        Ahora bien, nos parece bien que haya algún tipo de lock para que no modifiquen cosas que afectan esta
        liquidación, decidimos mantener el lock de odoo que aplica sobre tax_lock_date pero parechemaos para que
        este asiento se pueda publicar sin estar afetado por el lock.
        Otra alternativa sería solo hacer lock de ventas/compras, pero en tal caso nos podrían registrar pagos u
        otras cosas que afecten también IVA
        """
        if self.company_id.country_id.code == "AR" and self.move_id.closing_return_id:
            return False
        return super()._affect_tax_report() or self.move_id.closing_return_id
