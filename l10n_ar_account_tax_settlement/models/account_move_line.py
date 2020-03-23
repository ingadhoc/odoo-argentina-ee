from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # por ahora no extendemos, vamos a ver si lo resolvemos con etiquetas
    # def _get_tax_settlement_journal(self):
    #     """
    #     This method return the journal that can settle this move line
    #     """
    #     self.ensure_one()
    #     tax = self.tax_id.tax_group_id.tax
    #     if self.comapny_id.localization == 'argentina' and tax:
    #         return self.env['account.journal'].search([
    #             ('settlement_tax', '=', tax),
    #             ('company_id', '=', self.company_id.id)], limit=1)
    #     return super(AccountMoveLine, self)._get_tax_settlement_journal()
