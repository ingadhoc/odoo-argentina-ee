##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models, _
import datetime
from dateutil.relativedelta import relativedelta


class get_dates_wizard(models.TransientModel):
    _name = 'get_dates_wizard'
    _description = 'Wizard genérico para obtener fecha desde y hasta'

    @api.model
    def open_wizard(self, method):
        """
        Action to be called by other methods, method is the one that is going
        to be called after dates has been setted (on active_id and
        active_model)
        """
        context = self._context.copy()
        context.update({'method': method})
        return {
            'name': _('Set Dates'),
            'target': 'new',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'type': 'ir.actions.act_window',
            'context': context,
        }

    @api.model
    def default_get(self, fct_fields):
        res = super(get_dates_wizard, self).default_get(fct_fields)
        context = self._context
        to_string = fields.Date.to_string
        today = datetime.date.today()
        if context.get('quincenal'):
            if today.day > 15:
                res.update({
                    'from_date': today.strftime('%Y-%m-01'),
                    'to_date': today.strftime('%Y-%m-15'),
                })
            else:
                f_date = today + relativedelta(months=-1, day=16)
                t_date = today + relativedelta(day=1, days=-1)
                res.update({
                    'from_date': to_string(f_date),
                    'to_date': to_string(t_date),
                })
        # sugerimos fecha final hasta ultimo día mes anterior
        else:
            t_date = today + relativedelta(day=1, days=-1)
            res.update({'to_date': to_string(t_date)})
        return res

    from_date = fields.Date(
        'From Date',
        # required=True,
    )

    to_date = fields.Date(
        'To Date',
        required=True,
    )

    def confirm(self):
        self.ensure_one()
        method = self._context.get('method')
        active_model = self._context.get('active_model')
        active_id = self._context.get('active_id')

        rec = self.env[active_model].with_context(
            from_date=self.from_date, to_date=self.to_date).browse(active_id)
        return getattr(rec, method)()
