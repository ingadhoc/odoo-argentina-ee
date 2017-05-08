# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models


class AccountReportContextCommon(models.TransientModel):
    _inherit = "account.report.context.common"

    def _report_name_to_report_model(self):
        res = super(
            AccountReportContextCommon, self)._report_name_to_report_model()
        # res['']
        res['account_iva_f2002_report'] = 'account.iva_f2002.report'
        # res['account_ret_and_perc_report'] = 'account.ret_and_perc.report'
        res['account_invoice_by_state_sale'] = (
            'account.invoice_by_state.sale')
        res['account_invoice_by_state_purchase'] = (
            'account.invoice_by_state.purchase')
        return res

    def _report_model_to_report_context(self):
        res = super(
            AccountReportContextCommon, self)._report_model_to_report_context()
        res['account.iva_f2002.report'] = 'account.report.context.iva_f2002'
        # res['account.ret_and_perc.report'] = (
        #     'account.report.context.ret_and_perc')
        res['account.invoice_by_state.sale'] = (
            'account.report.context.invoice_by_state.sale')
        res['account.invoice_by_state.purchase'] = (
            'account.report.context.invoice_by_state.purchase')
        return res
