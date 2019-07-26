from odoo import api, fields, models, _
# from odoo.addons.web_grid.models import END_OF, STEP_BY, START_OF
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError


class MisCashFlowForecastLine(models.Model):

    _name = 'mis.cash_flow.forecast_line'
    _description = 'MIS Cash Flow Forecast Line'

    date = fields.Date(
        required=True,
        index=True,
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Account',
        required=True,
        help='The account of the forecast line is only for informative '
        'purpose',
    )
    name = fields.Char(
        required=True,
        default='/',
    )
    balance = fields.Float(
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.user.company_id.id,
        index=True,
    )

    def _get_adjust_grid_domain(self, column_value):
        # span is always daily and value is an iso range
        day = column_value.split('/')[0]
        return [('name', '=', False), ('date', '=', day)]

    @api.multi
    def adjust_grid(
            self, row_domain, column_field, column_value, cell_field, change):
        if column_field != 'date' or cell_field != 'balance':
            raise ValueError(
                "{} can only adjust balance (got {}) by date (got {})".format(
                    self._name,
                    cell_field,
                    column_field,
                ))

        additionnal_domain = self._get_adjust_grid_domain(column_value)
        domain = expression.AND([row_domain, additionnal_domain])
        line = self.search(domain)
        if len(line) > 1:
            raise UserError(_(
                'Multiple timesheet entries match the modified value. Please '
                'change the search options or modify the entries individually.'
            ))

        if line:  # update existing line
            line.write({
                cell_field: line[cell_field] + change
            })
        else:  # create new one
            day = column_value.split('/')[0]
            self.search(row_domain, limit=1).copy({
                column_field: day,
                cell_field: change
            })
        return False

    @api.constrains('company_id', 'account_id')
    def _check_company_id_employee_id(self):
        if self.filtered(lambda x: x.company_id != x.account_id.company_id):
            raise ValidationError(_(
                'The Company and the Company of the Account must be the '
                'same.'))
