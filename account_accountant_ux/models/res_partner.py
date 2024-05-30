# © 2017 Eficent Business and IT Consulting Services S.L.
#        (http://www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import ast
from odoo import models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    def action_open_reconcile(self):
        action_values = self.env['ir.actions.act_window']._for_xml_id('account_accountant.action_move_line_posted_unreconciled')
        domain = ast.literal_eval(action_values['domain'])
        domain.append(('partner_id', '=', self.id))
        action_values['domain'] = domain
        return action_values

    def open_partner_ledger(self):
        """ Heredamos y modificamos el método original que está en account reports y lo dejamos como estaba en 16
        para que al momento de hacer click en 'Saldo a pagar' en algún diario de liquidación de impuestos entonces se
        abra el libro mayor de empresas para el partner de liquidación, caso contrario, se van a visualizar los
        asientos contables de las liquidaciones de impuestos de ese diario propiamente dicho.
        Este método se llama en ../account_journal_dashboard.py en el método open_action.
        Esto no solo lo hacemos para tax_Settelement si no tmb para usabilidad general al usar el botón de ir a libro mayor
        desde la form de partners
        """
        action = self.env["ir.actions.actions"]._for_xml_id("account_reports.action_account_report_partner_ledger")
        action['params'] = {
            'options': {'partner_ids': [self.id]},
            'ignore_session': 'both',
        }
        return action

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
