from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    arba_cit = fields.Char(related='company_id.arba_cit', readonly=False)
