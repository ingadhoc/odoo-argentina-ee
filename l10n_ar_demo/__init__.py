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


old_load_manifest = module.load_manifest


def load_manifest(module_name, mod_path=None):
    info = old_load_manifest(module_name, mod_path=mod_path)
    if module_name in ['l10n_ar', 'l10n_ar_edi', 'l10n_ar_website_sale']:
        info['demo'] = []
    return info


module.load_manifest = load_manifest


def _load_l10n_ar_demo_data(cr):
    """
    Carga los datos demo de l10n_ar que fueron ocultados por load_manifest.
    Este hook se ejecuta antes de cargar los demos de l10n_ar_demo para asegurar
    que las dependencias (journals, productos, partners, etc) existan.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Verificar si los datos demo ya fueron cargados (para evitar recargas en upgrades)
    # Verificamos con company_exento que se crea en el primer archivo demo (exento_demo.xml)
    if env['ir.model.data'].search([('module', '=', 'l10n_ar'), ('name', '=', 'company_exento')], limit=1):
        _logger.info('Demo data from l10n_ar already loaded, skipping manual load')
        return

    # Desactivar constraints problemáticas temporalmente durante la carga inicial
    # Esto es necesario porque los archivos demo de l10n_ar tienen problemas de orden
    AccountJournal = env.registry['account.journal']
    orig_check1 = AccountJournal.check_use_document
    orig_check2 = AccountJournal._check_afip_configurations
    AccountJournal.check_use_document = lambda self: None
    AccountJournal._check_afip_configurations = lambda self: None

    try:
        for module_name in ['l10n_ar', 'l10n_ar_edi', 'l10n_ar_website_sale']:
            _logger.info('Loading demo data from %s' % module_name)
            manifest_file = module.module_manifest(module.get_module_path(module_name))
            f = tools.file_open(manifest_file, mode='rb')
            try:
                info = ast.literal_eval(tools.pycompat.to_text(f.read()))
            finally:
                f.close()
            for demo_data in info.get('demo', []):
                _logger.info('Loading %s', (demo_data))
                tools.convert_file(cr, module_name, demo_data, {}, 'init', True, 'demo', None)
            env.cr.commit()
    finally:
        # Restaurar constraints
        AccountJournal.check_use_document = orig_check1
        AccountJournal._check_afip_configurations = orig_check2
