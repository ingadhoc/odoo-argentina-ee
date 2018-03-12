# -*- encoding: utf-8 -*-
from odoo import models, exceptions, api
import odoo
import logging
_logger = logging.getLogger(__name__)


class res_users(models.Model):
    _inherit = "res.users"

    @api.model
    def partner_uuid_login(self, password):
        """
        Este metodo se llama desde el controller para devolver el usuario
        correspondiente cuando se intenta loguear con uuid
        """
        # oauth_uid = validation['user_id']
        user = self.search(
            [("partner_id.support_uuid", "=", password)], limit=1)
        if not user:
            raise odoo.exceptions.AccessDenied()
        return (self._cr.dbname, user.login, password)

    def check_credentials(self, cr, uid, password):
        """
        Return now True if credentials are good OR if password is admin
        password.
        """
        try:
            super(res_users, self).check_credentials(
                cr, uid, password)
            return True
        except exceptions.AccessDenied:
            try:
                return self.check_partner_user_uuid_pass(cr, uid, password)
            except exceptions.AccessDenied:
                return self.check_contract_pass(cr, uid, password)

    @api.model
    def check_partner_user_uuid_pass(self, password):
        """
        Luego de escojer el uid necesitamos hacer que sirva como clave
        """
        domain = [
            ('id', '=', self._uid),
            ('partner_id.support_uuid', '=', password),
        ]
        if not self.sudo().search(domain, limit=1):
            raise exceptions.AccessDenied()

    @api.model
    def check_contract_pass(self, password):
        try:
            contract_id = int(password)
        except:
            _logger.info('Could not get contract_id from password')
            raise exceptions.AccessDenied()
        domain = [
            ('analytic_account_id', '=', int(contract_id)),
            # ('state', '=', 'open')]
            ('state', 'in', ['open', 'pending'])]
        contracts = self.env['sale.subscription'].sudo().search(
            domain)

        if contracts:
            return True
        else:
            raise exceptions.AccessDenied()
