##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):

    """Loaded after installing the module.
    This module's DB modifications will be available.
    :param openerp.sql_db.Cursor cr:
        Database cursor.
    :param openerp.modules.registry.RegistryManager registry:
        Database registry, using v7 api.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.company'].set_special_defaults_on_install()
