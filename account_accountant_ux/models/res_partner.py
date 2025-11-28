# © 2017 Eficent Business and IT Consulting Services S.L.
#        (http://www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import ast

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = "res.partner"

    credit = fields.Monetary(search="_credit_search")  # pylint: disable=C8109
    debit = fields.Monetary(search="_debit_search")  # pylint: disable=C8109

    def action_open_reconcile(self):
        action_values = self.env["ir.actions.act_window"]._for_xml_id(
            "account_accountant.action_move_line_posted_unreconciled"
        )
        domain = ast.literal_eval(action_values["domain"])
        domain.append(("partner_id", "=", self.id))
        action_values["domain"] = domain
        return action_values

    def _open_report_action(self, report_action_xmlid, partner_ids=None):
        """Método genérico para abrir reportes de account_reports filtrados por partners

        Args:
            report_action_xmlid: XML ID de la acción del reporte a abrir
            partner_ids: Lista de IDs de partners. Si no se provee, usa self.id

        Returns:
            dict: Acción del reporte configurada
        """
        if partner_ids is None:
            partner_ids = [self.id]

        action = self.env["ir.actions.actions"]._for_xml_id(report_action_xmlid)
        action["params"] = {
            "options": {"partner_ids": partner_ids},
            "ignore_session": "both",
        }
        return action

    def _validate_mass_selection(self, max_partners=1000):
        """Valida que la selección masiva no exceda el límite permitido

        Args:
            max_partners: Número máximo de partners permitidos

        Returns:
            list: Lista de IDs de partners seleccionados

        Raises:
            UserError: Si se excede el límite de partners
        """
        selected_partner_ids = self.env.context.get("active_ids", [])
        if len(selected_partner_ids) >= max_partners:
            raise UserError(f"Se deben seleccionar menos de {max_partners} contactos")
        return selected_partner_ids

    def open_partner_ledger(self):
        """Heredamos y modificamos el método original que está en account reports y lo dejamos como estaba en 16
        para que al momento de hacer click en 'Saldo a pagar' en algún diario de liquidación de impuestos entonces se
        abra el libro mayor de empresas para el partner de liquidación, caso contrario, se van a visualizar los
        asientos contables de las liquidaciones de impuestos de ese diario propiamente dicho.
        Este método se llama en ../account_journal_dashboard.py en el método open_action.
        Esto no solo lo hacemos para tax_Settelement si no tmb para usabilidad general al usar el botón de ir a libro mayor
        desde la form de partners
        """
        return self._open_report_action("account_reports.action_account_report_partner_ledger")

    def open_mass_partner_ledger(self):
        partner_ids = self._validate_mass_selection()
        return self._open_report_action("account_reports.action_account_report_partner_ledger", partner_ids)

    def open_aged_receivable(self):
        """Abre el reporte de Aged Receivable filtrado por el partner actual"""
        return self._open_report_action("account_reports.action_account_report_ar")

    def open_mass_aged_receivable(self):
        partner_ids = self._validate_mass_selection()
        return self._open_report_action("account_reports.action_account_report_ar", partner_ids)

    def open_aged_payable(self):
        """Abre el reporte de Aged Payable filtrado por el partner actual"""
        return self._open_report_action("account_reports.action_account_report_ap")

    def open_mass_aged_payable(self):
        partner_ids = self._validate_mass_selection()
        return self._open_report_action("account_reports.action_account_report_ap", partner_ids)

    @api.model
    def _credit_search(self, operator, operand):
        if len(self.env.companies) > 1:
            domain = []
            for company in self.env.companies:
                cond = self.with_company(company.id)._asset_difference_search(
                    account_type="asset_receivable", operator=operator, operand=operand
                )
                if cond:
                    domain = expression.OR([domain or [], cond]) if domain else cond

            if not domain:
                return [("id", "=", 0)]

            return domain
        else:
            return super()._credit_search(operator, operand)

    @api.model
    def _debit_search(self, operator, operand):
        if len(self.env.companies) > 1:
            domain = []
            for company in self.env.companies:
                cond = self.with_company(company.id)._asset_difference_search(
                    account_type="liability_payable", operator=operator, operand=operand
                )
                if cond:
                    domain = expression.OR([domain or [], cond]) if domain else cond

            if not domain:
                return [("id", "=", 0)]

            return domain
        else:
            return super()._debit_search(operator, operand)
