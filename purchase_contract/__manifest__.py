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
    "name": "Purchase Contract",
    'version': '9.0.1.3.0',
    'category': 'Accounting',
    'sequence': 14,
    'summary': 'Contract Purchase, Invoicing',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        'purchase',
    ],
    'data': [
        'security/purchase_contract_security.xml',
        'security/ir.model.access.csv',
        'view/purchase_subscription_view.xml',
        'view/purchase_subscription_menu.xml',
        'data/subscription_cron.xml',
        'data/purchase_contract_data.xml'
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': False,
    'auto_install': False,
    'application': True,
}
