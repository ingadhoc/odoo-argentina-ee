from odoo import fields, models


class AccountMovetLine(models.Model):
    _inherit = "account.move.line"

    filter_amount = fields.Float(compute="_compute_filter_amout", search="_search_filter_amount")

    def _compute_filter_amout(self):
        self.filter_amount = False

    def _search_filter_amount(self, operator, value):
        res = []
        if self.env.context.get("default_st_line_id"):
            statement_line = self.env["account.bank.statement.line"].browse(self.env.context.get("default_st_line_id"))

            primary_currency = statement_line.company_id.currency_id == statement_line.currency_id
            if primary_currency:
                amount = statement_line["amount"]
                amount_currency = statement_line["amount_currency"]
            else:
                amount = statement_line["amount_currency"]
                amount_currency = statement_line["amount"]

            if value != 0 and operator == "=":
                if primary_currency:
                    base_amount = ((100 - value) / 100) * amount
                    top_amount = ((100 + value) / 100) * amount
                    res.append(("amount_residual", ">", base_amount))
                    res.append(("amount_residual", "<", top_amount))
                else:
                    base_amount = ((100 - value) / 100) * amount_currency
                    top_amount = ((100 + value) / 100) * amount_currency
                    res.append(("amount_residual_currency", ">", base_amount))
                    res.append(("amount_residual_currency", "<", top_amount))
            else:
                amount = ((100 - value) / 100) * amount
                amount_currency = ((100 - value) / 100) * amount_currency

                if primary_currency:
                    res.append(("amount_residual", operator, amount))
                else:
                    res.append(("amount_residual_currency", operator, amount_currency))
        return res
