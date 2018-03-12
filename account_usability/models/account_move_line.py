# -*- coding: utf-8 -*-
# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, api, fields
# from odoo.exceptions import UserError, ValidationError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    account_user_type_id = fields.Many2one(
        string='Account Type',
        related='account_id.user_type_id',
        store=True,
        readonly=True,
    )
    analytic_tag_ids = fields.Many2many(
        related='analytic_account_id.tag_ids',
        readonly=True,
        string='Analytic Tags',
    )

    @api.multi
    def action_open_related_document(self):
        self.ensure_one()
        # usamos lo que ya se usa en js para devolver la accion
        res_model, res_id, action_name, view_id = self.get_model_id_and_name()

        return {
            'type': 'ir.actions.act_window',
            'name': action_name,
            'res_model': res_model,
            'view_type': 'form',
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'res_id': res_id,
            # 'view_id': res[0],
        }
