##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, _


class CrmPhonecall(models.Model):
    _inherit = 'crm.phonecall'

    @api.multi
    def action_form_view(self):
        self.ensure_one()
        view = (
            'crm_voip_usability.crm_case_phone_form_view')
        return {
            'name': _('Phonecalls'),
            'target': 'current',
            'res_id': self.id,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'view_id': self.env.ref(view).id,
            'type': 'ir.actions.act_window',
        }
