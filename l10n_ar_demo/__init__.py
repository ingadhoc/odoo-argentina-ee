##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, SUPERUSER_ID
from odoo.modules import module
import odoo.tools as tools
import ast
import logging


_logger = logging.getLogger(__name__)


old_load_information_from_description_file = module.load_information_from_description_file


def load_information_from_description_file(module, mod_path=None):
    info = old_load_information_from_description_file(module, mod_path=mod_path)
    if module in ['l10n_ar', 'l10n_ar_edi', 'l10n_ar_website_sale']:
        info['demo'] = []
    return info


module.load_information_from_description_file = load_information_from_description_file


def _load_l10n_ar_demo_data(cr):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for module_name in ['l10n_ar', 'l10n_ar_edi', 'l10n_ar_website_sale']:
        _logger.info('Loading demo data from %s' % module_name)
        manifest_file = module.module_manifest(module.get_module_path(module_name))
        f = tools.file_open(manifest_file, mode='rb')
        try:
            info = ast.literal_eval(tools.pycompat.to_text(f.read()))
        finally:
            f.close()
        for demo_data in info.get('demo'):
            _logger.info('Loading %s', (demo_data))
            tools.convert_file(cr, module_name, demo_data, {}, 'init', True, 'demo', None)
        env.cr.commit()
