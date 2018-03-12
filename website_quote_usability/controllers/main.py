# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.web.http import request
from odoo.addons.website_quote.controllers.main import sale_quote


class sale_quote_contract(sale_quote):
    @http.route()
    def view(self, order_id, pdf=None, token=None, message=False, **kw):
        response = super(sale_quote_contract, self).view(
            order_id, pdf, token, message, **kw)
        # check if token identification was ok in super
        if 'quotation' in response.qcontext:
            tx_id = response.qcontext['tx_id']
            if tx_id:
                tx = request.env['payment.transaction'].sudo().browse(tx_id)
                response.qcontext['tx_error_msg'] = (
                    tx.state_message or tx.acquirer_id.error_msg)
        return response
