# -*- encoding: utf-8 -*-
from openerp import models, exceptions, api
import logging
_logger = logging.getLogger(__name__)


class res_users(models.Model):
    _inherit = "res.users"

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
            return self.check_contract_pass(cr, uid, password)

    @api.model
    def check_contract_pass(self, password):
        try:
            contract_id = int(password)
        except:
            _logger.info('Could not get contract_id from password')
            raise exceptions.AccessDenied()
        domain = [
            ('analytic_account_id', '=', contract_id),
            ('state', '=', 'open')]
        contracts = self.env['sale.subscription'].sudo().search(
            domain)

        if contracts:
            return True
        else:
            raise exceptions.AccessDenied()
