##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    @api.multi
    def update_lines_prices_from_products(self):
        for contract in self:
            for line in contract.recurring_invoice_line_ids:
                partner = line.analytic_account_id.partner_id
                pricelist = line.analytic_account_id.pricelist_id
                company = line.analytic_account_id.company_id
                # we dont send name because we want to update it
                vals = line.product_id_change(
                    line.product_id.id, line.uom_id.id, qty=line.quantity,
                    name='', partner_id=partner.id, price_unit=False,
                    pricelist_id=pricelist.id, company_id=company.id).get(
                    'value', {})
                # we use setattr instead of write so tax_id m2m field can be
                # setted
                for k, v in vals.iteritems():
                    setattr(line, k, v)
