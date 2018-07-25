from odoo import http
from odoo.http import request


class WebsiteQuotePublished(http.Controller):

    @http.route(
        ["/quote/public_template/<model('sale.quote.template'):quote>"],
        type='http', auth="public", website=True)
    def public_template_view(self, quote, **post):
        quote = quote.sudo()
        values = {'template': quote}
        return request.render(
            'website_quote_public.so_template_public', values)
