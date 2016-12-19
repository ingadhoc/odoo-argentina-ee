# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api, _
import base64
import logging
_logger = logging.getLogger(__name__)


# because of compatibility with v8 we keep this
class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    @api.model
    def create_issue(
            self, contract_id, db_name, login,
            vals, attachments_data):
        return self.env['sale.subscription'].create_issue(
            contract_id, db_name, login, vals, attachments_data)


class SaleSubscription(models.Model):
    _inherit = 'sale.subscription'

    @api.model
    def create_issue(
            self, analytic_account_id, db_name, login,
            vals, attachments_data):
        _logger.info('Creating issue for contract %s, db %s, login %s' % (
            analytic_account_id, db_name, login))
        contract = self.sudo().search([
            ('analytic_account_id', '=', int(analytic_account_id)),
            ('state', '=', 'open')], limit=1)
        if not contract:
            return {'error': _(
                "No open contract for id %s" % analytic_account_id)}
        database = self.env['infrastructure.database'].sudo().search([
            ('name', '=', db_name), ('contract_id', '=', contract.id),
            ('state', '=', 'active')],
            limit=1)
        if not database:
            return {'error': _(
                "No database found")}
        _logger.info('Looking for user with login %s on database id %s' % (
            login, database.id))

        vals['database_id'] = database.id
        user = database.user_ids.search([
            ('database_id', '=', database.id), ('login', '=', login)], limit=1)
        if not user:
            return {'error': _(
                "User is not registered on support provider database")}

        if not user.authorized_for_issues:
            return {'error': _(
                "User is not authorized to register issues")}
        vals['partner_id'] = user.partner_id.id
        vals['email_from'] = user.partner_id.email

        project = self.env['project.project'].sudo().search(
            [('analytic_account_id', '=',
                contract.analytic_account_id.id)], limit=1)
        if project:
            vals['project_id'] = project.id

        issue = self.env['project.issue'].sudo().create(vals)
        # suscribe partner
        issue.message_subscribe([user.partner_id.id])

        attachments = []
        for data in attachments_data:
            attachments.append(
                (data['name'], base64.b64decode(data['datas'])))
            # we use b64decode because it will be encoded by message_post
            # attachments.append((data['name'], data['datas']))
        issue.message_post(
            body=None, subject=None, attachments=attachments)

        res = {'issue_id': issue.id}

        # try to add title
        try:
            server_issue_title = self.env['ir.config_parameter'].get_param(
                'server_issue_title')
            res['title'] = server_issue_title
        except:
            _logger.warning('Could not get server issue title')
            pass

        # try to add message
        try:
            server_issue_message = self.env['ir.config_parameter'].get_param(
                'server_issue_message')
            res['message'] = server_issue_message % (issue.id)
        except:
            _logger.warning('Could not get server issue message')
            pass

        return res
