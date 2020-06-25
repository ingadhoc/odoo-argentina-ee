# flake8: noqa
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from odoo.tools import float_is_zero, float_compare, pycompat
from odoo import models, api, _


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    @api.model
    def _get_payments_vals(self):
        res = super(AccountInvoice, self)._get_payments_vals()
        for payment in res:
            move = self.env['account.move'].browse(payment['move_id'])
            payment['ref'] = move.display_name
        return res

    @api.one
    def _get_outstanding_info_JSON(self):
        self.outstanding_credits_debits_widget = json.dumps(False)
        if self.state == 'open':
            domain = [('account_id', '=', self.account_id.id),
                      ('partner_id', '=', self.env['res.partner']._find_accounting_partner(self.partner_id).id),
                      ('reconciled', '=', False),
                      '|',
                        '&', ('amount_residual_currency', '!=', 0.0), ('currency_id','!=', None),
                        '&', ('amount_residual_currency', '=', 0.0), '&', ('currency_id','=', None), ('amount_residual', '!=', 0.0)]
            if self.type in ('out_invoice', 'in_refund'):
                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                type_payment = _('Outstanding credits')
            else:
                domain.extend([('credit', '=', 0), ('debit', '>', 0)])
                type_payment = _('Outstanding debits')
            info = {'title': '', 'outstanding': True, 'content': [], 'invoice_id': self.id}
            lines = self.env['account.move.line'].search(domain)
            currency_id = self.currency_id
            if len(lines) != 0:
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == self.currency_id:
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        # as we dont add the currency information we use the rate of the invoice that is the one used by odoo compute amount_residual
                        # INICIO CAMBIO
                        amount_to_show = line.company_id.currency_id.with_context(date=self.date_invoice).compute(abs(line.amount_residual), self.currency_id)
                        # amount_to_show = line.company_id.currency_id.with_context(date=line.date).compute(abs(line.amount_residual), self.currency_id)
                        # FIN CAMBIO
                    if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                        continue
                    if line.ref :
                        # INICIO CAMBIO
                        title = '%s : %s' % (line.move_id.display_name, line.ref)
                        # title = '%s : %s' % (line.move_id.name, line.ref)
                        # FIN CAMBIO
                    else:
                        # INICIO CAMBIO
                        title = line.move_id.display_name
                        # title = line.move_id.name
                        # FIN CAMBIO
                    info['content'].append({
                        # INICIO CAMBIO
                        'journal_name': line.ref or line.move_id.display_name,
                        # 'journal_name': line.ref or line.move_id.name,
                        # FIN CAMBIO
                        'title': title,
                        'amount': amount_to_show,
                        'currency': currency_id.symbol,
                        'id': line.id,
                        'position': currency_id.position,
                        'digits': [69, self.currency_id.decimal_places],
                    })
                info['title'] = type_payment
                self.outstanding_credits_debits_widget = json.dumps(info)
                self.has_outstanding = True
