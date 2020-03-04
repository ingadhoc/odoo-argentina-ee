##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api


class AccountChangeLockDate(models.TransientModel):
    _inherit = 'account.change.lock.date'

    company_id = fields.Many2one(
        'res.company',
        'Company',
        default=lambda self: self.env.user.company_id,
        required=True,
    )

    @api.onchange('company_id')
    def onchange_company_id(self):
        self.period_lock_date = self.company_id.period_lock_date
        self.fiscalyear_lock_date = self.company_id.fiscalyear_lock_date
        self.tax_lock_date = self.company_id.tax_lock_date

    def change_lock_date(self):
        self.company_id.sudo().write({
            'period_lock_date': self.period_lock_date,
            'fiscalyear_lock_date': self.fiscalyear_lock_date,
            'tax_lock_date': self.tax_lock_date,
        })
        return {'type': 'ir.actions.act_window_close'}
