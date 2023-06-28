from odoo import models, api
from odoo.tools.misc import formatLang

class BankRecWidget(models.Model):
    _inherit = "bank.rec.widget"

    @api.depends('st_line_id')
    def _compute_amls_widget(self):
        for wizard in self:
            super()._compute_amls_widget()
            amls_widget = wizard.amls_widget
            amls_widget['context']['default_st_line_id'] = wizard.st_line_id.id
            amls_widget['context']['search_default_same_amount'] = True
            wizard.amls_widget = amls_widget

    def collect_global_info_data(self, journal_id):

        # Por ahora no mostramos el valor en el kanban. Porque confunde al cliente 
        # Deberiaamos aplicar este Cambio a como esta en master 17 ¿usar patch?
        # Ver commit
        # https://github.com/odoo/enterprise/commit/e1f0f66a7237d8c8b056cdf2636ccc019818a17d#diff-ee342c09ffb6b8de7f51c4a0ed66fee056e8975e7416d0f85ae0d2b6b1883dfdR1467

        # journal = self.env['account.journal'].browse(journal_id)
        # balance = formatLang(self.env,
        #                      journal.current_statement_balance,
        #                      currency_obj=journal.currency_id or journal.company_id.currency_id)
        # return {
        #     'balance_amount': balance,
        # }

        return {'balance_amount': None}
