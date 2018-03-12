# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
# import datetime
import werkzeug
from odoo import http
from odoo.http import request
# from werkzeug.exceptions import NotFound
from odoo.addons.website_portal.controllers.main import website_account


class PortalInfrastructureWebsiteAccount(website_account):

    @http.route([
        '/my/duplicate_database/<int:database_id>/',
    ],
        type='http',
        auth="user",
        # auth="public",
        website=True)
    def old_duplicate_database(
            self, database_id, message='', message_class='', **kw):
        request.env['res.users'].browse(request.uid).has_group(
            'base.group_sale_salesman')
        database = request.env['infrastructure.database'].browse(database_id)
        database_type = request.env['infrastructure.database_type'].search([
            ('is_production', '=', False), ('portal_visible', '=', True)],
            limit=1)
        if database_type:
            database.instance_id.duplicate(
                database.environment_id,
                database_type,
            )
        # TODO tiene que haber una forma mas elegante de devolver el mismo
        # lugar en el que estamos
        return werkzeug.utils.redirect(
            '/my/contract_databases/%i/' % database.contract_id.id)

    @http.route([
        '/my/delete_database/<int:database_id>/',
    ],
        type='http',
        auth="user",
        # auth="public",
        website=True)
    def old_delete_database(
            self, database_id, message='', message_class='', **kw):
        request.env['res.users'].browse(request.uid).has_group(
            'base.group_sale_salesman')
        database = request.env['infrastructure.database'].browse(database_id)
        contract = database.contract_id
        database.instance_id.delete()
        database.instance_id.unlink()
        # TODO tiene que haber una forma mas elegante de devolver el mismo
        # lugar en el que estamos
        return werkzeug.utils.redirect(
            '/my/contract_databases/%i/' % contract.id)

    @http.route([
        '/my/contract_databases/<int:account_id>/',
    ],
        type='http',
        auth="user",
        # auth="public",
        website=True)
    def old_contract_databases(
            self, account_id, uuid='', message='', message_class='', **kw):
        """
        No usamos ni mandamos lo de uuid porque lo hicimos privado
        """
        request.env['res.users'].browse(request.uid).has_group(
            'base.group_sale_salesman')
        account_res = request.env['sale.subscription']
        account = account_res.browse(account_id)

        values = {
            'account': account,
            'user': request.env.user,
        }
        return request.website.render(
            "website_infrastructure_contract.contract_databases", values)
