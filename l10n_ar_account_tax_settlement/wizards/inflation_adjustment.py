##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import formatLang, format_date
from dateutil.relativedelta import relativedelta


class InflationAdjustment(models.TransientModel):

    _name = 'inflation.adjustment'
    _description = 'Inflation adjustment'

    date_from = fields.Date(
        required=True,
    )
    date_to = fields.Date(
        required=True,
    )
    journal_id = fields.Many2one(
        'account.journal',
        domain=[('type', '=', 'general')],
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
    )
    account_id = fields.Many2one(
        'account.account',
        domain=[('deprecated', '=', False)],
        required=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        'Analytic Account',
    )
    start_index = fields.Float(
        compute='_compute_index',
        )
    end_index = fields.Float(
        compute='_compute_index',
        )
    open_cloure_entry = fields.Selection(
         [('yes', 'Si'),
          ('no', 'No')],
        string="Ha realizado asientos de cierre/apertura?",
        default='no',
        help="Si usted ha realizado los asientos de cierre/apertura debe"
        " indicarnos cuales son para poder excluir los mismos en el cálculo."
    )
    closure_move_id = fields.Many2one(
        'account.move',
        string="Asiento de cierre",
    )
    open_move_id = fields.Many2one(
        'account.move',
        string="Asiento de apertura",
    )

    @api.model
    def default_get(self, field_list):
        res = super(InflationAdjustment, self).default_get(field_list)
        today = fields.Datetime.now()
        company = self.env.company
        res['company_id'] = company.id
        company_fiscalyear_dates = company.compute_fiscalyear_dates(
            (today - relativedelta(year=today.year-1)))
        for key, value in company_fiscalyear_dates.items():
            company_fiscalyear_dates[key] = value
        res.update(company_fiscalyear_dates)
        return res

    @api.depends('date_from', 'date_to')
    def _compute_index(self):
        """ Update index when dates has been updated, raise a warning when
        the index period does not exist
        """
        # res = {}
        # msg = str()
        index_obj = self.env['inflation.adjustment.index']
        start_index = index_obj.find(self.date_from)
        end_index = index_obj.find(self.date_to)
        self.start_index = start_index.value
        self.end_index = end_index.value

    def get_periods(self, start_date=None, end_date=None):
        """ return a list of periods were the inflation adjustment will be
        apply.

        If not found index in any of the months in the selected period then
        a UserError exception will be thrown

        :return: [{
          'date_from': <first_date_month>, (for first period date_from date)
          'date_to': <last_date_month>,
          'factor': end_index / <month_index>,
          'index': recordset('inflation.adjustment.index')}, ...]
        """
        if self:
            self.ensure_one()
            start_date = self.date_from
            end_date = self.date_to
            end_index = self.end_index
        else:
            end_index = self.env['inflation.adjustment.index'].find(
                end_date).value

        if not start_date or not end_date:
            raise UserError(_(
                'Por favor indique el rango de fecha de inicio y fin'))

        res = []
        cur_date = start_date
        end = end_date

        indexes = self.env['inflation.adjustment.index'].search([])

        while cur_date < end:
            date_to = cur_date + relativedelta(months=1, days=-1)
            if date_to > end:
                date_to = end

            index = indexes.filtered(
                lambda x: x.date >= cur_date and x.date < date_to)
            if not index:
                raise UserError(_(
                    'El asiento de ajuste por inflación no puede ser generado'
                    ' ya que hace falta el indice de ajuste para el periodo'
                    ' %s %s' % (
                        cur_date.strftime("%B"), cur_date.year)))

            res.append({
                'date_from': cur_date,
                'date_to': date_to,
                'index': index,
                'factor': (end_index / index.value) - 1.0,
            })
            cur_date += relativedelta(months=1, day=1)
        return res

    def get_move_line_domain(self):
        self.ensure_one()
        no_monetaria_tag = self.env.ref('l10n_ar_ux.no_monetaria_tag')
        res = [
            ('account_id.tag_ids', 'in', no_monetaria_tag.id),
            ('company_id', '=', self.company_id.id),
            ('move_id.state', '=', 'posted'),
        ]
        if self.open_move_id:
            res += [('move_id', '!=', self.open_move_id.id)]
        if self.closure_move_id:
            res += [('move_id', '!=', self.closure_move_id.id)]
        return res

    def confirm(self):
        """ Search all the related account.move.line and will create the
        related inflation adjustment journal entry for the specification.
        """
        def FormatAmount(amount):
            return formatLang(
                self.env, amount, currency_obj=self.company_id.currency_id)

        self.ensure_one()
        account_move_line = self.env['account.move.line']
        adjustment_total = {'debit': 0.0, 'credit': 0.0}
        lines = []

        # Generate account.move.line adjustment for start of the period
        domain = self.get_move_line_domain()
        domain += [
            ("account_id.user_type_id.include_initial_balance", '=', True),
            ('date', '<', self.date_from)]
        init_data = account_move_line.read_group(
            domain, ['account_id', 'balance'], ['account_id'],
        )
        date_from = self.date_from
        date_to = self.date_to
        before_date_from = self.date_from + relativedelta(months=-1)
        before_index = self.env['inflation.adjustment.index'].find(before_date_from)

        periods = self.env['inflation.adjustment'].get_periods(before_date_from, self.date_from)

        initial_factor = (self.end_index / before_index.value) - 1.0
        for line in init_data:
            adjustment = line.get('balance') * initial_factor
            if self.company_id.currency_id.is_zero(adjustment):
                continue
            else:
                adjustment = self.company_id.currency_id.round(adjustment)
            lines.append({
                'account_id': line.get('account_id')[0],
                'name': _('Ajuste por inflación cuentas al inicio '
                '(%s * %.2f%%)') % (
                    FormatAmount(line.get('balance')), initial_factor * 100.0),
                'date_maturity': before_date_from,
                'debit' if adjustment > 0 else 'credit': abs(adjustment),
                'analytic_account_id': self.analytic_account_id.id,
            })
            adjustment_total[
                'debit' if adjustment > 0 else 'credit'] += abs(adjustment)

        # Get period month list
        periods = self.get_periods()

        for period in periods:
            # search account.move.lines
            domain = self.get_move_line_domain()
            domain += [('date', '>=', period.get('date_from')),
                       ('date', '<=', period.get('date_to'))]
            data = account_move_line.read_group(
                domain, ['account_id', 'balance'], ['account_id', 'date'])
            date_from = period.get('date_from')
            for line in data:
                adjustment = line.get('balance') * period.get('factor')
                if self.company_id.currency_id.is_zero(adjustment):
                    continue
                else:
                    adjustment = self.company_id.currency_id.round(adjustment)
                lines.append({
                    'account_id': line.get('account_id')[0],
                    'name': _('Ajuste por inflación %s '
                    '(%s * %.2f%%)') % (
                        format_date(self.env, date_from, date_format='MM/Y'),
                        FormatAmount(line.get('balance')),
                        period.get('factor') * 100.0),
                    'date_maturity': period.get('date_from'),
                    'debit' if adjustment > 0 else 'credit': abs(adjustment),
                    'analytic_account_id': self.analytic_account_id.id,
                })
                adjustment_total[
                    'debit' if adjustment > 0 else 'credit'] += abs(adjustment)

        if not lines:
            raise UserError(_(
                "No hemos encontrado ningún asiento contable asociado al"
                " periodo seleccionado."
            ))

        # Generate total amount adjustment line
        adj_diff = adjustment_total.get('debit', 0.0) - adjustment_total.get(
            'credit', 0.0)
        lines.append({
            'account_id': self.account_id.id,
            'name': _('Ajuste por inflación Global [%s] / [%s]') % (
                self.date_from, self.date_to),
            'debit' if adj_diff < 0 else 'credit': abs(adj_diff),
            'date_maturity': self.date_to,
            'analytic_account_id': self.analytic_account_id.id,
        })

        # Generate account.move
        move = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'date': self.date_to,
            'ref': _('Ajuste por inflación %s') % (date_to.year),
            'line_ids': [(0, 0, line_data) for line_data in lines],
        })
        return move.get_access_action()
