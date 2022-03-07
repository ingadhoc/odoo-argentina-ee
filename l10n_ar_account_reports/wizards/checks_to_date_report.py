##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields

class AccountCheckToDateReportWizard(models.TransientModel):
    _name = 'account.check.to_date.report.wizard'
    _description = 'account.check.to_date.report.wizard'

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        domain=[
            '|',
            ('outbound_payment_method_ids.code', '=', 'issue_check'),
            ('inbound_payment_method_ids.code', '=', 'received_third_check'),
            ],
    )
    to_date = fields.Date(
        'Hasta Fecha',
        required=True,
        default=fields.Date.today,
    )

    def action_confirm(self):
        self.ensure_one()
        force_domain = self.journal_id and [
            ('check_id.journal_id', '=', self.journal_id.id)] or []

        # cheques de tercero en mano
        third_ops = self.env['account.check']._get_checks_to_date_on_state(
            'holding', self.to_date, force_domain=force_domain).sorted(key=lambda r:r.check_id.payment_date or r.check_id.issue_date)
        # cheques propios entregados
        issue_ops = self.env['account.check']._get_checks_to_date_on_state(
            'handed', self.to_date, force_domain=force_domain).sorted(key=lambda r:r.check_id.payment_date or r.check_id.issue_date)

        datadict = {
            'third_ops_ids': third_ops.ids,
            'issue_ops_ids': issue_ops.ids,
            'date': self.to_date.strftime('%d/%m/%Y'),
            'journal': self.journal_id.id
        }

        return self.env.ref('l10n_ar_account_reports.checks_to_date_report').report_action([], data=datadict)
