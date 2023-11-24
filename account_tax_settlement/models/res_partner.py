from odoo import models


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'


    def open_partner_ledger(self):
        """ Heredamos y modificamos el método original que está en account reports y lo dejamos como estaba en 16 para que al momento de hacer click en 'Saldo a pagar' en algún diario de liquidación de impuestos entonces se abra el libro mayor de empresas para el partner de liquidación, caso contrario, se van a visualizar los asientos contables de las liquidaciones de impuestos de ese diario propiamente dicho. Este método se llama en ../account_journal_dashboard.py en el método open_action. """
        action = self.env["ir.actions.actions"]._for_xml_id("account_reports.action_account_report_partner_ledger")
        action['params'] = {
            'options': {'partner_ids': [self.id]},
            'ignore_session': 'both',
        }
        return action
