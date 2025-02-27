##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models


class AccountReconcileWizard(models.TransientModel):
    _inherit = "account.reconcile.wizard"

    multiple_partners = fields.Boolean(compute="_compute_multiple_partners")

    @api.depends("move_line_ids.partner_id")
    @api.depends_context("active_ids")
    def _compute_multiple_partners(self):
        for wizard in self:
            wizard.multiple_partners = False
            active_ids = self.env.context.get("active_ids")
            if active_ids:
                partner_ids = self.env["account.move.line"].browse(active_ids).mapped("move_id.partner_id")
                if len(set(partner_ids)) > 1:
                    wizard.multiple_partners = True
