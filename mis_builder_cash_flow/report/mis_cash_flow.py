from odoo import api, fields, models, tools


class MisCashFlow(models.Model):

    _name = 'mis.cash_flow'
    _description = 'MIS Cash Flow'
    _auto = False

    # line_type = fields.Char()
    line_type = fields.Selection(
        [('forecast_line', 'Forecast Line'), ('move_line', 'Journal Item')],
    )
    name = fields.Char(
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Account',
    )
    move_line_id = fields.Many2one(
        comodel_name='account.move.line',
        string='Journal Item',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
    )
    credit = fields.Float(
    )
    debit = fields.Float(
    )
    date = fields.Date(
    )
    reconciled = fields.Boolean(
    )
    user_type_id = fields.Many2one(
        'account.account.type',
    )

    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        query = """
            SELECT ROW_NUMBER() OVER() AS id, mis_cash_flow.* FROM (
            SELECT
                'move_line' as line_type,
                aml.id as move_line_id,
                aml.account_id as account_id,
                aml.debit as debit,
                aml.credit as credit,
                aml.reconciled as reconciled,
                aml.company_id as company_id,
                aml.user_type_id as user_type_id,
                aml.name as name,
                CASE
                    WHEN aat.type IN ('receivable', 'payable') and
                        aml.expected_pay_date is not null
                            THEN aml.expected_pay_date
                    WHEN aat.type IN ('receivable', 'payable') and
                        aml.date_maturity is not null
                            THEN aml.date_maturity
                    ELSE aml.date
                END AS date
            FROM account_move_line as aml
            JOIN account_account_type aat ON aml.user_type_id = aat.id
            UNION
            SELECT
                'forecast_line' as line_type,
                Null as move_line_id,
                fl.account_id as account_id,
                CASE
                    WHEN fl.balance > 0
                    THEN fl.balance
                    ELSE 0.0
                END AS debit,
                CASE
                    WHEN fl.balance < 0
                    THEN -fl.balance
                    ELSE 0.0
                END AS credit,
                False as reconciled,
                fl.company_id as company_id,
                aa.user_type_id as user_type_id,
                fl.name as name,
                fl.date as date
            FROM mis_cash_flow_forecast_line as fl
            JOIN account_account aa ON aa.id = fl.account_id
            ) as mis_cash_flow

        """
        self._cr.execute("""CREATE or REPLACE VIEW %s as (%s
        )""" % (self._table, query))

    @api.multi
    def action_open_related_document(self):
        self.ensure_one()
        return self.move_line_id.action_open_related_document()
