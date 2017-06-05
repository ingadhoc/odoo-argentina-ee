# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api, fields, _
from openerp.exceptions import UserError


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    template_dates_required = fields.Boolean(
        "Dates Required",
    )
    dates_required = fields.Boolean(
        related="template_id.template_dates_required",
        readonly=True,
    )

    @api.model
    def _prepare_invoice_data(self, contract):
        res = super(SaleSubscription, self)._prepare_invoice_data(contract)
        if contract.company_id.copy_contract_description:
            res.update({'comment': contract.description})
        return res

    @api.multi
    def set_open(self):
        return self.write({'state': 'open'})

    @api.multi
    @api.constrains('date', 'date_start')
    def validate_dates(self):
        for sub in self:
            if sub.date and sub.date_start and sub.date < sub.date_start:
                raise UserError(
                    _("The date end must be grater than the start date!"))
