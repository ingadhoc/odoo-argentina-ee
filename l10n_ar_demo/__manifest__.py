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
    'name': 'More demo data for Argentina Localization (Enterprise version)',
    'version': "15.0.1.0.0",
    'category': 'Accounting',
    'sequence': 14,
    'summary': '',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        'account_accountant_ux',
        'l10n_ar_edi_ux',
        'l10n_ar_ux',
        'l10n_ar_account_tax_settlement',
        'l10n_ar_account_withholding',
        'l10n_ar_website_sale',
    ],
    'data': [
    ],
    'demo': [
        'demo/account_tax_demo.xml',
        'demo/customer_payment_demo.xml',
        'demo/supplier_payment_demo.xml',
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'pre_init_hook': '_load_l10n_ar_demo_data'
}
