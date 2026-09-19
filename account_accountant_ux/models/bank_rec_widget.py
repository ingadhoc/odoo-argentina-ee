<<<<<<< HEAD
||||||| MERGE BASE
=======
from odoo import Command, models

# from odoo.tools.misc import formatLang
from odoo.exceptions import UserError


class BankRecWidget(models.Model):
    _inherit = "bank.rec.widget"

    def _get_rec_pay_matching_domain(self):
        """Dominio del filtro "Cliente/Proveedor" del tablero de conciliación.

        El de core pide ``payment_id != False`` en la rama de las cuentas de pagos pendientes,
        así que ahí solo entran los asientos que son el asiento de un ``account.payment``.
        Cualquier otro asiento que viva en esas cuentas queda clasificado como "Misc" y el filtro
        lo esconde, aunque sea exactamente lo que el usuario está buscando conciliar: el caso que
        motivó esto es el débito de un cheque propio, que se asienta contra la cuenta de pagos
        pendientes del diario pero no tiene pago de origen.

        Como acá abajo dejamos el filtro activo por default, esconder esos apuntes obliga al
        usuario a sacar el filtro para encontrarlos. Alcanza con que la línea esté en una cuenta
        de pagos pendientes del diario: si no está conciliada y vive ahí, es una contrapartida de
        pago legítima.
        """
        self.ensure_one()
        journal = self.st_line_id.journal_id
        outstanding_accounts = (
            journal._get_journal_inbound_outstanding_payment_accounts()
            | journal._get_journal_outbound_outstanding_payment_accounts()
        ) - journal.default_account_id
        return [
            "|",
            # Facturas.
            "&",
            ("account_id.account_type", "in", ("asset_receivable", "liability_payable")),
            ("payment_id", "=", False),
            # Contrapartidas de pagos.
            ("account_id", "in", outstanding_accounts.ids),
        ]

    def _prepare_embedded_views_data(self):
        data = super()._prepare_embedded_views_data()
        data["amls"]["context"]["default_st_line_id"] = self.st_line_id.id

        dynamic_filters = {
            dynamic_filter.get("name"): dynamic_filter for dynamic_filter in data["amls"].get("dynamic_filters", [])
        }
        rec_pay_filter = dynamic_filters.get("receivable_payable_matching")
        if rec_pay_filter:
            # Activate the partner filter by default
            rec_pay_filter["is_default"] = True
            domain = self._get_rec_pay_matching_domain()
            # super() ya dejó los dominios stringificados, así que los reemplazamos igual de armados.
            rec_pay_filter["domain"] = str(domain)
            misc_filter = dynamic_filters.get("misc_matching")
            if misc_filter:
                misc_filter["domain"] = str(["!"] + domain)

        if bool(self.env["ir.config_parameter"].sudo().get_param("account_accountant_ux.use_search_filter_amount")):
            data["amls"]["context"]["search_default_same_amount"] = True
        return data

    # def collect_global_info_data(self, journal_id):

    #     journal = self.env['account.journal'].browse(journal_id)
    #     balance = formatLang(self.env,
    #                          journal.current_statement_balance,
    #                          currency_obj=journal.currency_id or journal.company_id.currency_id)
    #     return {
    #         'balance_amount': balance,
    #     }

    def _lines_recompute_exchange_diff(self, lines):
        self.ensure_one()
        self._ensure_loaded_lines()

        line_ids_commands = []

        # Clean the existing lines.
        for exchange_diff in self.line_ids.filtered(lambda x: x.flag == "exchange_diff"):
            line_ids_commands.append(Command.unlink(exchange_diff.id))

        new_amls = self.line_ids.filtered(lambda x: x.flag == "new_aml")
        if self.company_id.reconcile_on_company_currency:
            accounts_currency_ids = []
            for new_aml in new_amls:
                if new_aml.account_id.currency_id not in accounts_currency_ids:
                    accounts_currency_ids.append(new_aml.account_id.currency_id)
            if len(accounts_currency_ids) > 1:
                raise UserError(
                    "No puede conciliar en el mismo registro apuntes de cuentas con moneda secundaria y apuntes sin "
                    'cuando tiene configurada la compañía con "Reconcile On Company Currency"'
                )
            if not accounts_currency_ids or not accounts_currency_ids[0]:
                line_ids_commands = []

                # Clean the existing lines.
                for exchange_diff in self.line_ids.filtered(lambda x: x.flag == "exchange_diff"):
                    line_ids_commands.append(Command.unlink(exchange_diff.id))

                    self.line_ids = line_ids_commands
                return
        super()._lines_recompute_exchange_diff(lines)

>>>>>>> FORWARD PORTED
