##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def sync_padron_afip(cr, registry):
    """ Try to sync data from padron """
    _logger.info('Syncking afip padron data')
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        account_config = env['res.config.settings']
        account_config.refresh_from_padron("impuestos")
        account_config.refresh_from_padron("conceptos")
        account_config.refresh_from_padron("actividades")
    except Exception:
        pass


def post_init_hook(cr, registry):
    """Loaded after installing the module """
    _logger.info('Post init hook initialized')
    sync_padron_afip(cr, registry)
