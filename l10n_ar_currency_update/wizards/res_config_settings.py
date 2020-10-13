##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    rate_perc = fields.Float(related="company_id.rate_perc", readonly=False)
    rate_surcharge = fields.Float(related="company_id.rate_surcharge", readonly=False)
