# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api, fields


class account_check_to_date_report_wizard(models.TransientModel):
    _name = 'account.check.to_date.report.wizard'

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        domain=[('payment_subtype', '=', 'issue_check')],
    )
    to_date = fields.Date(
        'Hasta Fecha',
        required=True,
        default=fields.Date.today,
    )

    @api.multi
    def action_confirm(self):
        self.ensure_one()
        force_domain = self.journal_id and [
            ('check_id.journal_id', '=', self.journal_id.id)] or []

        # cheques de tercero en mano
        third_ops = self.env['account.check']._get_checks_to_date_on_state(
            'holding', self.to_date, force_domain=force_domain)
        # cheques propios entregados
        issue_ops = self.env['account.check']._get_checks_to_date_on_state(
            'handed', self.to_date, force_domain=force_domain)

        return self.env['report'].with_context(
            issue_op_ids=issue_ops.ids,
            third_op_ids=third_ops.ids,).get_action(
            self, 'account_checks_to_date_report')
