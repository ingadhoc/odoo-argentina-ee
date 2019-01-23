from odoo import api, fields, models, tools


class MisCashFlow(models.Model):

    _name = 'mis.cash_flow'
    _description = 'MIS Cash Flow'
    _auto = False

    # line_type = fields.Char()
    line_type = fields.Selection(
        [('forecast_line', 'Forecast Line'), ('move_line', 'Journal Item')],
        index=True,
        readonly=True,
    )
    name = fields.Char(
        readonly=True,
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Account',
        auto_join=True,
        index=True,
        readonly=True,
    )
    move_line_id = fields.Many2one(
        comodel_name='account.move.line',
        string='Journal Item',
        auto_join=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        auto_join=True,
        readonly=True,
        index=True,
    )
    credit = fields.Float(
        readonly=True,
    )
    debit = fields.Float(
        readonly=True,
    )
    date = fields.Date(
        readonly=True,
        index=True,
    )
    reconciled = fields.Boolean(
        readonly=True,
    )
    user_type_id = fields.Many2one(
        'account.account.type',
        auto_join=True,
        readonly=True,
        index=True,
    )

    @api.model_cr
    def init(self):
        """ TODO find another alternative instead of multiplying
        aml.id * 10000.
        We do it that way because if we use "SELECT ROW_NUMBER() OVER()..."
        the performance was very poor (due to the union of two tables I think)
        """
        query = """
            SELECT
                aml.id * 10000 as id,
                CAST('move_line' AS varchar) as line_type,
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
            UNION ALL
            SELECT
                fl.id as id,
                CAST('forecast_line' AS varchar) as line_type,
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
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self._cr.execute("""CREATE or REPLACE VIEW %s as (%s
        )""" % (self._table, query))

    @api.multi
    def action_open_related_document(self):
        self.ensure_one()
        return self.move_line_id.action_open_related_document()

    @api.multi
    def action_open_related_line(self):
        self.ensure_one()
        if self.line_type == 'move_line':
            return self.move_line_id.get_formview_action()
        else:
            return self.env['mis.cash_flow.forecast_line'].browse(
                self.id).get_formview_action()
