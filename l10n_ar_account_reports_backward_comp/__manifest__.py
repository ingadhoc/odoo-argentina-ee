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
    "name": "Backward compatibility for tax Settlements on Argentina",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "LGPL-3",
    "images": [],
    "depends": [
        "l10n_ar_tax_backward_compatibility",
        "l10n_ar_account_reports",
<<<<<<< 7c65563e40d7c7c5a5a451f1148643e07e4f3aa9:l10n_ar_account_reports_backward_comp/__manifest__.py
||||||| c3ca3929e55e1c32adb31dc23f1e50003c2d6c45:l10n_ar_account_tax_settlement/__manifest__.py
        "l10n_ar_ux",
        "l10n_ar_tax",
        "account_payment_pro_receiptbook",
    ],
    "data": [
        "data/inflation_adjustment_index.xml",
        "data/ir_actions_server.xml",
        "data/account_report_data.xml",
        "views/inflation_adjustmen_index_view.xml",
        "views/account_tax_view.xml",
        "wizards/inflation_adjustment_view.xml",
        "security/ir.model.access.csv",
=======
        "l10n_ar_ux",
        "l10n_ar_tax",
        "account_payment_pro_receiptbook",
    ],
    "data": [
        "data/inflation_adjustment_index.xml",
        "data/ir_actions_server.xml",
        "data/account_report_data.xml",
        "views/inflation_adjustmen_index_view.xml",
        "views/account_tax_view.xml",
        "views/account_payment_view.xml",
        "wizards/inflation_adjustment_view.xml",
        "wizards/tax_settlement_reassign_view.xml",
        "security/ir.model.access.csv",
>>>>>>> 912a09d0ba54adf12c24c92aa065fab6cf102687:l10n_ar_account_tax_settlement/__manifest__.py
    ],
    "data": [],
    "demo": [],
    "test": [],
    "installable": True,
    "auto_install": True,
    "application": False,
}
