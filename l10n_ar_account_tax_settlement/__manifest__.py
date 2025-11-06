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
    "name": "Tax Settlements For Argentina",
<<<<<<< a826cb679ea41690662ab500d3503189dc8be8df
    "version": "18.0.1.6.0",
||||||| 67839d789e2297847b7c94998e8ea2ce6695dbdf
    "version": "18.0.1.7.0",
=======
    "version": "18.0.1.8.0",
>>>>>>> 7d75348b4e148be47ccca5e92a1837797638d360
    "category": "Accounting",
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "LGPL-3",
    "images": [],
    "depends": [
        "account_tax_settlement",
        "account_ux",
        "l10n_ar",
        "l10n_ar_account_reports",
        "l10n_ar_ux",
        "l10n_ar_tax",
        "account_payment_pro_receiptbook",
    ],
    "data": [
        "data/inflation_adjustment_index.xml",
        "data/ir_actions_server.xml",
        "views/inflation_adjustmen_index_view.xml",
        "views/account_tax_view.xml",
        "wizards/inflation_adjustment_view.xml",
        "security/ir.model.access.csv",
    ],
    "demo": [],
    "test": [],
    "installable": False,
    "auto_install": ["l10n_ar"],
    "application": False,
    "post_init_hook": "l10n_ar_account_tax_settlement_post_init_hook",
}
