# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.multi
    def action_general_ledger(self):
        # TODO ver si podemos usar la modificacion que hicmos en
        # account_general_ledger para mandar por contexto las cuentas
        # contables que se deben mostrar (para no mostrar todas)
        self.ensure_one()
        ctx = self.env.context.copy()
        ctx.update({
            'url': '/account_reports/output_format/general_ledger/1',
            'model': 'account.general.ledger',
        })
        # coo el force_account acepta solo una solo lo hacemos sin son la misma
        if self.default_debit_account_id and self.default_debit_account_id == \
                self.default_credit_account_id:
            ctx.update({
                'active_id': self.default_credit_account_id.id,
                # TODO ver como forzar compania de la cuenta
                # 'company_ids': self.default_credit_account_id.company_id.id,
                'force_account': True,
                'addActiveId': True,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'account_report_generic',
            'context': ctx,
        }
