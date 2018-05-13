# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api, modules, tools
from openerp.modules.module import adapt_version
from openerp.exceptions import ValidationError
from openerp.addons.adhoc_modules_server.octohub.connection import Connection
# from octohub.connection import Connection
from openerp.addons.server_mode.mode import get_mode
from openerp.tools.parse_version import parse_version
import base64
import logging
import itertools
import os

_logger = logging.getLogger(__name__)
MANIFEST = '__openerp__.py'
README = ['README.rst', 'README.md', 'README.txt']


def load_information_from_contents(
        manifest_content, readme_content=False, index_content=False):
    """
    :param module: The name of the module (sale, purchase, ...)
    :param mod_path: Physical path of module, if not providedThe name of the
        module (sale, purchase, ...)
    """

    # default values for descriptor
    info = {
        'application': False,
        'author': '',
        'auto_install': False,
        'category': 'Uncategorized',
        'depends': [],
        'description': '',
        # 'icon': get_module_icon(module),
        'installable': True,
        'license': 'AGPL-3',
        'post_load': None,
        'version': '1.0',
        'web': False,
        'website': '',
        'sequence': 100,
        'summary': '',
    }
    info.update(itertools.izip(
        'depends data demo test init_xml update_xml demo_xml'.split(),
        iter(list, None)))
    try:
        info.update(eval(manifest_content))
    except:
        _logger.warning('could not ')
        return {}
    # if not info.get('description'):
    #     readme_path = [opj(mod_path, x) for x in README
    #                    if os.path.isfile(opj(mod_path, x))]
    #     if readme_path:
    #         readme_text = tools.file_open(readme_path[0]).read()
    #         info['description'] = readme_text

    if 'active' in info:
        # 'active' has been renamed 'auto_install'
        info['auto_install'] = info['active']

    info['version'] = adapt_version(info['version'])
    return info


class AdhocModuleRepository(models.Model):
    _name = 'adhoc.module.repository'
    _inherit = ['mail.thread']
    _rec_name = 'display_name'

    user = fields.Char(
        'User or Organization',
        required=True,
        help='eg. "ingadhoc"',
    )
    subdirectory = fields.Char(
        'Subdirectory',
        help='For eg. "addons"',
    )
    name = fields.Char(
        'Repository Name',
        required=True,
        help='eg. "product"',
    )
    branch = fields.Selection(
        [('8.0', '8.0'), ('9.0', '9.0'), ('11.0', '11.0')],
        'Branch / Odoo Version',
        required=True,
    )
    module_ids = fields.One2many(
        'adhoc.module.module',
        'repository_id',
        'Modules',
    )
    token = fields.Char(
        help='If no token configured, we will try to use a general one setted '
        'as "github.token" parameter, if none configured, we try connecting '
        'without token'
    )
    auto_update = fields.Boolean(
        default=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    display_name = fields.Char(
        compute='get_display_name',
        store=True,
    )

    @api.one
    @api.depends('user', 'name', 'branch')
    def get_display_name(self):
        self.display_name = "%s/%s:%s" % (
            self.user or '',
            self.name or '',
            self.branch or '',
        )

    @api.multi
    def get_token(self):
        self.ensure_one()
        token = self.token
        if not token:
            token = self.env['ir.config_parameter'].get_param(
                'github.token') or ''
        return token

    @api.multi
    def get_connection(self):
        self.ensure_one()
        token = self.get_token()
        return Connection(token)

    @api.multi
    def get_modules_paths(self):
        """return name of remote modules"""
        response = self.read_remote_path(self.subdirectory or '')
        paths = [x['path'] for x in response.parsed if x['type'] == 'dir']
        _logger.info('Readed paths %s' % paths)
        return paths

    @api.multi
    def read_remote_path(self, path=False):
        _logger.info('Reading data from remote path %s' % path)
        conn = self.get_connection()
        # obtener directorios
        uri = "/repos/%s/%s/contents/%s" % (
            self.user, self.name, path or '')
        try:
            response = conn.send(
                'GET', uri, params={'ref': self.branch})
        except Exception, ResponseError:
            raise ValidationError(
                'Could not get modules for:\n'
                '* Repository: %s\n'
                '* URI: %s\n'
                '* Branch: %s\n'
                '* Token: %s\n\n'
                'This is what we get:%s' % (
                    self.name, uri, self.branch,
                    self.get_token(), ResponseError))
        return response

    @api.model
    def get_module_info(self, name):
        descriptor = {'8.0': '__openerp__.py',
                      '9.0': '__openerp__.py',
                      '11.0': '__manifest__.py'}
        info = {}
        try:
            response = self.read_remote_path("%s/%s" % (
                name, descriptor.get(self.branch, '__manifest__.py')))
            encoded_content = response.parsed['content']
            info = load_information_from_contents(
                base64.b64decode(encoded_content))
        except Exception:
            _logger.debug('Error when trying to fetch informations for '
                          'module %s', name, exc_info=True)
        return info

    @api.multi
    def get_module_vals(self, info):
        self.ensure_one()

        vals = {
            'description': info.get('description', ''),
            'shortdesc': info.get('name', ''),
            'author': info.get('author', 'Unknown'),
            'maintainer': info.get('maintainer', False),
            'contributors': ', '.join(info.get('contributors', [])) or False,
            'website': info.get('website', ''),
            'license': info.get('license', 'AGPL-3'),
            'sequence': info.get('sequence', 100),
            # 'new_sequence': info.get('sequence', 100),
            'application': info.get('application', False),
            'auto_install': info.get('auto_install', False),
            'icon': info.get('icon', False),
            'summary': info.get('summary', ''),
        }
        # TODO faltaria ver si lo reseteamos si no es mas auto_install
        if info.get('auto_install', False):
            vals['conf_visibility'] = 'auto_install_by_code'
        return vals

    @api.model
    def _cron_scan_repositories(self):
        if get_mode():
            _logger.info(
                'Scan repositories is disable by server_mode. '
                'If you want to enable it you should remove develop or test '
                'value for server_mode key on openerp server config file')
            return False
        for repository in self.search([('auto_update', '=', True)]):
            try:
                repository.scan_repository()
                self._cr.commit()
            except:
                # TODO we should set a last update in each repository and
                # make cron run more frequently
                _logger.error("Error updating repository %s" % (
                    repository.name))

    @api.multi
    def scan_repository(self):
        self.ensure_one()
        _logger.info("Scaning repository %s" % (self.name))
        res = [0, 0]    # [update, add]
        errors = []

        default_version = modules.adapt_version('1.0')

        # iterate through detected modules and update/create them in db
        for module_path in self.get_modules_paths():
            # sacamos la ultima parte del path como nombre del modulo
            mod_name = os.path.basename(module_path)
            # search for modules of same name an odoo version
            mod = self.env['adhoc.module.module'].search([
                ('name', '=', mod_name),
                ('repository_id.branch', '=', self.branch)], limit=1)
            module_info = self.get_module_info(module_path)
            values = self.get_module_vals(module_info)

            if mod:
                _logger.info('Updating data for module %s' % mod_name)
                if mod.repository_id.id != self.id:
                    msg = ('Module %s already exist in repository %s' % (
                        mod_name, mod.repository_id.name))
                    errors.append(msg)
                    _logger.warning(msg)
                    continue
                updated_values = {}
                # if mod alread y exist, we pop new_sequence value because
                # we dont want to update it
                values.pop('sequence')
                # values.pop('new_sequence')
                for key in values:
                    old = getattr(mod, key)
                    updated = isinstance(
                        values[key], basestring) and tools.ustr(
                        values[key]) or values[key]
                    if (old or updated) and updated != old:
                        updated_values[key] = values[key]
                # we do not use state
                # if module_info.get(
                #         'installable', True) and mod.state == 'uninstallable':
                #     updated_values['state'] = 'uninstalled'
                if parse_version(module_info.get(
                        'version', default_version)) > parse_version(
                        mod.latest_version or default_version):
                    res[0] += 1
                if updated_values:
                    mod.write(updated_values)
            else:
                _logger.info('Creating new module %s' % mod_name)
                # if not installable, we dont upload
                if not module_info or not module_info.get(
                        'installable', True):
                    continue
                mod = mod.create(dict(
                    name=mod_name,
                    repository_id=self.id, **values))
                res[1] += 1
            mod._update_dependencies(module_info.get('depends', []))
        self.message_post(
            body="%s. Errors: %s" % (res, errors), subject=None)
        return res
