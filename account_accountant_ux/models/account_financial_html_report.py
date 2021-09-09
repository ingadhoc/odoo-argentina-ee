##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class ReportAccountFinancialHtmlReport(models.Model):
    _inherit = "account.financial.html.report"

    def button_create_menu_and_action(self):
        self._create_action_and_menu(self.parent_id.id)

    def _create_action_and_menu(self, parent_id):
        super(ReportAccountFinancialHtmlReport,
              self.sudo())._create_action_and_menu(parent_id=parent_id)
