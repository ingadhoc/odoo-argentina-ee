##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    use_company_currency_on_followup = fields.Boolean()
    use_search_filter_amount = fields.Boolean(
        string="Filter by same amount",
        default=True
        )
