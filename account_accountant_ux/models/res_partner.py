from odoo import models
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'
    
    def open_mass_partner_ledger(self):
        selected_partner_ids = self.env.context.get('active_ids')
        if len(selected_partner_ids) < 1000:
        
            action = self.env["ir.actions.actions"]._for_xml_id("account_reports.action_account_report_partner_ledger")
            action['params'] = {

                'options': {'partner_ids': selected_partner_ids},
                'ignore_session': 'both',
            }
            return action
        else:
            raise UserError('Se deben seleccionar menos de 1000 contactos')
