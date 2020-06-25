from odoo import fields, models, api
# from odoo.exceptions import ValidationError


class AccountTax(models.Model):
    _inherit = 'account.tax'

    settlement_journal_id = fields.Many2one(
        'account.journal',
        string='Settlement Journal',
        compute='_compute_settlement_journal',
    )

    @api.multi
    @api.depends('tag_ids')
    def _compute_settlement_journal(self):
        for rec in self:
            rec.settlement_journal_id = rec.env['account.journal'].search([
                ('settlement_account_tag_ids', 'in', rec.tag_ids.ids),
                ('company_id', '=', rec.company_id.id)], limit=1)
