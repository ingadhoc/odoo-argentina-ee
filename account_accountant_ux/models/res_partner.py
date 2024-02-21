# © 2017 Eficent Business and IT Consulting Services S.L.
#        (http://www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import ast
from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_open_reconcile(self):
        action_values = self.env['ir.actions.act_window']._for_xml_id('account_accountant.action_move_line_posted_unreconciled')
        domain = ast.literal_eval(action_values['domain'])
        domain.append(('partner_id', '=', self.id))
        action_values['domain'] = domain
        return action_values
