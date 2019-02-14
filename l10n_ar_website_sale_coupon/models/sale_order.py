##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models


class SaleOrder(models.Model):

    _inherit = "sale.order"

    report_reward_amount = fields.Float(
        compute='_compute_report_reward_amount',
    )

    @api.depends('order_line')
    def _compute_report_reward_amount(self):
        for rec in self:
            if rec.vat_discriminated:
                rec.report_reward_amount = sum([
                    line.price_subtotal
                    for line in rec._get_reward_lines()])
            else:
                rec.report_reward_amount = sum([
                    line.price_unit_with_tax
                    for line in rec._get_reward_lines()])
