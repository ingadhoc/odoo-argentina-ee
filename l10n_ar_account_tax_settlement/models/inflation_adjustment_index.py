from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class InflationAdjustmentIndex(models.Model):

    _name = 'inflation.adjustment.index'
    _description = 'Inflation Adjustment Index'
    _order = 'date desc'
    _rec_name = 'date'

    date = fields.Date(
        required=True,
    )
    value = fields.Float(
        required=True,
        digits=(12,4),
    )
    xml_id = fields.Char(compute='_compute_xml_id', string="External ID")

    @api.depends()
    def _compute_xml_id(self):
        res = self.get_external_id()
        for action in self:
            action.xml_id = res.get(action.id)

    @api.model
    def find(self, date, closest=False):
        """ :return: recordset (empty if not found)
        """
        range = self.get_dates(date)
        return self.search([
            ('date', '>=', range.get('date_from')),
            ('date', '<=', range.get('date_to')),
        ], limit=1)

    @api.constrains('date')
    def check_date_unique(self):
        for rec in self:
            repeated = self.find(rec.date)
            if len(repeated) > 1:
                rec_date = fields.Date.from_string(rec.date)
                raise ValidationError(_(
                    "Ya existe un indice para el periodo %s %s. Solo"
                    " puedes tener un indice de inflación por mes" % (
                        rec_date.strftime("%B"), rec_date.year)))

    @api.constrains('date')
    def check_day(self):
        for rec in self:
            date = fields.Date.from_string(rec.date)
            if date.day != 1:
                raise ValidationError(_(
                    "El indice debe comenzar el primer día de cada mes"))

    @api.constrains('date')
    def check_xml_id(self):
        """ always create the xml_id when create a new record of this model.
        """
        if self.env.context.get('install_mode', False):
            return

        model_data = self.env['ir.model.data']
        for rec in self.filtered(lambda x: not x.xml_id):
            date = fields.Date.from_string(rec.date)
            metadata = {
                'name': 'index_%02d_%s' % (date.month, date.year),
                'model': self._name,
                'module': 'l10n_ar_account_tax_settlement',
                'res_id': rec.id,
                'noupdate': True,
            }
            model_data.create(metadata)

    def get_dates(self, date=None):
        """ Get the begining and end date of a period.

        if self is set then will return the index of the period.
        If not then will take into account the date given to
        compute the begin/end of the month where this date belong

        :return: dictionary of of the form
            {'date_from': 'YYYY-MM-DD' ,'date_to': 'YYYY-MM-DD'}
        """
        if self:
            self.ensure_one()
            date = self.date

        to_string = fields.Date.to_string
        date_from = fields.Date.from_string(date) + relativedelta(day=1)
        # TODO NOT sure is this is ok
        date_to = date_from + relativedelta(months=1, days=-1)
        res = {
            'date_from': to_string(date_from),
            'date_to': to_string(date_to),
        }
        return res
