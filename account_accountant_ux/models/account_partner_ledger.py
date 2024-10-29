from odoo import models


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def open_journal_items(self, options, params):
        # Modificamos las vistas para que use las nuestras de account_ux en vez de las de partner grouped
        res = super().open_journal_items(options, params)
        res['search_view_id'] = [self.env.ref('account_ux.view_account_partner_ledger_filter').id, 'search']
        res['views'] = [(self.env.ref('account.view_move_line_payment_tree').id, 'list')]
        res.get('context', {}).update({'search_default_group_by_partner': 1})
        return res
