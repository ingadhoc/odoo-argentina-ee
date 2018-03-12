##############################################################################
#
#    Copyright (C) 2015  ADHOC SA  (http://www.adhoc.com.ar)
#    All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Infrastructure and Contracts Integration',
    'version': '9.0.1.4.0',
    'description': """
Infrastructure Contract
=======================
Provides integration between infrastructure module and web_support modules.
Add on infrastructure databases a link to contracts and the posibility to
upload the contract to the database.
Destiny database must have web_support_client module installed
    """,
    'category': u'base.module_category_knowledge_management',
    'author': u'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'depends': [
        'infrastructure',
        'sale_contract',
        # modulo requerido para obtener data de que productos contrataron
        'adhoc_modules_server',
        'web_support_server',
    ],
    'sequence': 14,
    'summary': '',
    'installable': False,
    'auto_install': True,
    'application': False,
    'images': [],
    'data': [
        'views/database_view.xml',
        'views/sale_subscription_view.xml',
        'views/odoo_version_view.xml',
        'views/product_template_view.xml',
        'data/sale_subscription_data.xml',
    ],
    'demo': [
        'demo/product_template_demo.xml',
        'demo/database_demo.xml',
    ],
    'test': [],
}
