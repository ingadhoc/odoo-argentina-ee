# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    @api.model
    def _prepare_invoice_data(self, contract):
        res = super(SaleSubscription, self)._prepare_invoice_data(contract)
        if contract.company_id.copy_contract_description:
            res.update({'internal_notes': contract.description})
        return res
