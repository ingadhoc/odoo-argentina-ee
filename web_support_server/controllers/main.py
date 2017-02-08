import logging

from openerp import http, SUPERUSER_ID
import werkzeug
from openerp.addons.web.controllers.main import ensure_db
from openerp.modules.registry import RegistryManager
from openerp.addons.web.controllers.main import (
    db_monodb, set_cookie_and_redirect, login_and_redirect)
_logger = logging.getLogger(__name__)


class OAuthController(http.Controller):

    @http.route('/partner_uuid/signin', type='http', auth='none')
    def signin(self, **kw):
        # TODO faltaria implementar el redirect y no hardcodear el my/home
        ensure_db()
        partner_uuid = kw['partner_uuid']
        dbname = kw.pop('db', None)
        if not dbname:
            dbname = db_monodb()
        if not dbname:
            return werkzeug.exceptions.BadRequest()
        registry = RegistryManager.get(dbname)
        with registry.cursor() as cr:
            url = '/my/home'
            try:
                u = registry.get('res.users')
                credentials = u.partner_uuid_login(
                    cr, SUPERUSER_ID, partner_uuid)
                cr.commit()
                return login_and_redirect(*credentials, redirect_url=url)
            except:
                pass
        return set_cookie_and_redirect(url)
