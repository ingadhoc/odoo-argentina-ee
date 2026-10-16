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
    "name": "Accounting Accountant UX",
    "version": "19.0.1.17.0",
    "category": "Accounting",
    "sequence": 14,
    "summary": "",
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "AGPL-3",
    "images": [],
    "depends": [
        "account_reports",
        "account_internal_transfer",
        "account_ux",
        "account_followup",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_company_view.xml",
        "views/res_partner_view.xml",
        "views/account_move_line.xml",
        "views/account_report_view.xml",
        "static/src/components/bank_reconciliation/button_list/assets.xml",
        "wizards/account_change_lock_date_views.xml",
        "wizards/account_reconcile_wizard.xml",
        "wizards/account_tax_settlement_wizard_views.xml",
        "data/account_accountant_data.xml",
        "views/account_journal_dashboard_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "account_accountant_ux/static/src/components/account_report/filters/filters.js",
            "account_accountant_ux/static/src/components/account_report/controller.js",
            "account_accountant_ux/static/src/account_report_filters_patch.js",
<<<<<<< 3df2457e5fe67e90f7bd3c05c09dcdb6e7b38819
            "account_accountant_ux/static/src/components/account_report/warnings.xml",
        ]
||||||| 51f3402624ed80d5cb7bfa5ce1a9c4922280c302
        ],
=======
            "account_accountant_ux/static/src/move_line_list_reconcile_patch.js",
        ],
>>>>>>> f295052e2584b2a6aabe53e3191e9d0ac69b4805
    },
    "post_init_hook": "post_init_hook",
    "demo": [],
    "installable": True,
    "auto_install": True,
    "application": False,
}
