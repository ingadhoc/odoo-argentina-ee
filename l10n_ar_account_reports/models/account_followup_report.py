# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import models, api
from datetime import datetime
# from hashlib import md5
from openerp.tools.misc import formatLang
from openerp.tools.translate import _
# import time
# from openerp.tools.safe_eval import safe_eval
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
# from openerp.tools import append_content_to_html
# import math


class report_account_followup_report(models.AbstractModel):
    _inherit = "account.followup.report"

    @api.model
    def get_lines(self, context_id, line_id=None, public=False):
        # res = super(report_account_followup_report, self).get_lines(
        #     context_id, line_id=line_id, public=public)

        # Get date format for the lang
        lang_code = context_id.partner_id.lang or self.env.user.lang or 'en_US'
        lang_ids = self.env['res.lang'].search(
            [('code', '=', lang_code)], limit=1)
        date_format = lang_ids.date_format or DEFAULT_SERVER_DATE_FORMAT

        def formatLangDate(date):
            date_dt = datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT)
            return date_dt.strftime(
                date_format.encode('utf-8')).decode('utf-8')

        lines = []
        res = {}
        today = datetime.today().strftime('%Y-%m-%d')
        line_num = 0
        # we use debt lines instead of move lines
        # we use commercial partner instead of partner to fix this for portal
        # user / contacts
        commercial_partner = context_id.partner_id.commercial_partner_id
        for l in commercial_partner.unreconciled_adl_ids:
            if public and l.blocked:
                continue
            # nativamente odoo separa la deuda en usd y en ars en distintas
            # secciones, nosotros las juntamos
            currency = l.company_id.currency_id
            # currency = l.currency_id or l.company_id.currency_id
            if currency not in res:
                res[currency] = []
            res[currency].append(l)
        for currency, aml_recs in res.items():
            total = 0
            total_issued = 0
            aml_recs = sorted(aml_recs, key=lambda aml: aml.blocked)
            for aml in aml_recs:
                # odoo separa por monedas, nosotros lo juntamos
                amount = aml.amount_residual
                # amount = (
                #     aml.currency_id and aml.amount_residual_currency or
                #     aml.amount_residual)
                date_due = formatLangDate(aml.date_maturity or aml.date)
                total += not aml.blocked and amount or 0
                is_overdue = (
                    today > aml.date_maturity if aml.date_maturity
                    else today > aml.date)
                is_payment = aml.payment_group_id
                if is_overdue or is_payment:
                    total_issued += not aml.blocked and amount or 0
                if is_overdue:
                    date_due = (date_due, 'color: red;')
                if is_payment:
                    date_due = ''
                amount = formatLang(self.env, amount, currency_obj=currency)
                line_num += 1
                lines.append({
                    'id': aml.id,
                    'name': aml.document_number,
                    # 'name': aml.move_id.name,
                    'action': aml.get_model_id_and_name(),
                    # 'move_id': aml.move_id.id,
                    'type': is_payment and 'payment' or 'unreconciled_aml',
                    'footnotes': {},
                    'unfoldable': False,
                    'columns': [
                        formatLangDate(aml.date),
                        date_due,
                        aml.invoice_id.name or aml.name
                    ] + (
                        not public and [aml.expected_pay_date and (
                            aml.expected_pay_date, aml.internal_note) or
                            ('', ''), aml.blocked] or []
                    ) + [amount],
                    'blocked': aml.blocked,
                })
            total = formatLang(self.env, total, currency_obj=currency)
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'type': 'total',
                'footnotes': {},
                'unfoldable': False,
                'level': 0,
                'columns': (
                    not public and ['', ''] or []) + [
                        '', '', total >= 0 and _('Total Due') or ''] + [total],
            })
            if total_issued > 0:
                total_issued = formatLang(
                    self.env, total_issued, currency_obj=currency)
                line_num += 1
                lines.append({
                    'id': line_num,
                    'name': '',
                    'type': 'total',
                    'footnotes': {},
                    'unfoldable': False,
                    'level': 0,
                    'columns': (not public and ['', ''] or []) + [
                        '', '', _('Total Overdue')] + [total_issued],
                })
        return lines
