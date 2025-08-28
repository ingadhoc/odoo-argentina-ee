from odoo import _, models, api, Command
# from odoo.tools.misc import formatLang
from odoo.exceptions import UserError

class BankRecWidget(models.Model):
    _inherit = "bank.rec.widget"

    def _prepare_embedded_views_data(self):
        data = super()._prepare_embedded_views_data()
        data['amls']['context']['default_st_line_id'] = self.st_line_id.id

        if bool(self.env['ir.config_parameter'].sudo().get_param('account_accountant_ux.use_search_filter_amount')):
            data['amls']['context']['search_default_same_amount'] = True
        return data


    # def collect_global_info_data(self, journal_id):

    #     journal = self.env['account.journal'].browse(journal_id)
    #     balance = formatLang(self.env,
    #                          journal.current_statement_balance,
    #                          currency_obj=journal.currency_id or journal.company_id.currency_id)
    #     return {
    #         'balance_amount': balance,
    #     }


    def _lines_recompute_exchange_diff(self):
        self.ensure_one()
        self._ensure_loaded_lines()

        line_ids_commands = []

        # Clean the existing lines.
        for exchange_diff in self.line_ids.filtered(lambda x: x.flag == 'exchange_diff'):
            line_ids_commands.append(Command.unlink(exchange_diff.id))

        new_amls = self.line_ids.filtered(lambda x: x.flag == 'new_aml')
        if self.company_id.reconcile_on_company_currency:

            accounts_currency_ids = []
            for new_aml in new_amls:
                if new_aml.account_id.currency_id not in accounts_currency_ids:
                    accounts_currency_ids.append(new_aml.account_id.currency_id)
            if len(accounts_currency_ids) > 1:
                raise UserError(
                    'No puede conciliar en el mismo registro apuntes de cuentas con moneda secundaria y apuntes sin '
                    'cuando tiene configurada la compañía con "Reconcile On Company Currency"')
            if not accounts_currency_ids or not accounts_currency_ids[0]:
                line_ids_commands = []

                # Clean the existing lines.
                for exchange_diff in self.line_ids.filtered(lambda x: x.flag == 'exchange_diff'):
                    line_ids_commands.append(Command.unlink(exchange_diff.id))

                    self.line_ids = line_ids_commands
                return
<<<<<<< d89eba0357a9b379002e061286bf9e2b7b1c9b14
        super()._lines_recompute_exchange_diff()
||||||| 5027c49c8d670f114fb1df4ea500e6adf738ab80
        super()._lines_widget_recompute_exchange_diff()
=======
        super()._lines_widget_recompute_exchange_diff()

    def button_validate(self, async_action=False):
        if self.form_account_id and self.form_account_id.analytic_distribution_required and not self.analytic_distribution:
            raise UserError(
                'No puede validar la conciliación porque la cuenta transitoria "%s" requiere una cuenta analítica'
                ' y no se ha configurado ninguna. Elimine la linea manualmente para volver a seleccionar la cuenta con su analitica' % self.form_account_id.name
            )
        super().button_validate(async_action=async_action)
>>>>>>> eae9a090af19c43ec3d547fd6dae875944b1f82c
