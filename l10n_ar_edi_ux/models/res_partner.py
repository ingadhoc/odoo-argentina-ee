from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def button_update_partner_data_from_padron(self):
        """Open the Argentina partner update wizard for this partner"""
        self.ensure_one()
        wiz = (
            self.env["res.partner.update.from.padron.wizard"]
            .with_context(active_ids=self.ids, active_model=self._name)
            .create({})
        )
        wiz.change_partner()
        action = self.env["ir.actions.actions"]._for_xml_id("l10n_ar_edi_ux.action_partner_update")
        action["res_id"] = wiz.id
        return action
