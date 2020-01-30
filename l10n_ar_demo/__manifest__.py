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
    'version': '12.0.1.0.0',
    'category': 'Accounting',
    'sequence': 14,
    'summary': '',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        'account_accountant',
        'l10n_ar_afipws_fe',
        'l10n_ar_chart',
        'l10n_ar_account_tax_settlement',
        'l10n_ar_account_withholding',
    ],
    'data': [
    ],
    'demo': [
        # De l10n_ar_chart
        # para datos demo agregamos alicuotas a las percepciones aplicadas y
        # sufridas
        '../l10n_ar_account/demo/account_tax_template_demo.xml',
        '../l10n_ar_chart/demo/account_chart_template.xml',
        '../l10n_ar_account/demo/account_journal_demo.xml',
        '../l10n_ar_account/demo/product_product_demo.xml',
        '../l10n_ar_account/demo/account_customer_invoice_demo.xml',
        '../l10n_ar_account/demo/account_customer_expo_invoice_demo.xml',
        '../l10n_ar_account/demo/account_customer_invoice_validate_demo.xml',
        '../l10n_ar_account/demo/account_customer_refund_demo.xml',
        '../l10n_ar_account/demo/account_supplier_invoice_demo.xml',
        '../l10n_ar_account/demo/account_supplier_invoice_validate_demo.xml',
        '../l10n_ar_account/demo/account_supplier_refund_demo.xml',

        # de l10n_ar_account_withholding
        'demo/customer_payment_demo.xml',
        'demo/supplier_payment_demo.xml',

        # de l10n_ar_afipws_fe
        '../l10n_ar_afipws_fe/demo/account_journal_expo_demo.xml',
        '../l10n_ar_afipws_fe/demo/account_journal_demo.xml',
    ],
    'test': [
    ],
    'installable': False,
    'auto_install': False,
    'application': False,
}
