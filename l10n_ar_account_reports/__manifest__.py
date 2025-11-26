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
    "name": "Accounting Reports Customized for Argentina",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "sequence": 14,
    "summary": "",
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "AGPL-3",
    "images": [],
    "depends": [
        "account_reports",
        # "l10n_ar_tax",
        "l10n_ar_withholding",
        "l10n_latam_check",
        "l10n_ar_reports",
    ],
    "data": [
        "data/tags_data.xml",
        "data/estado_resultados.xml",
        "data/balance_sheet.xml",
        "views/menu_reports.xml",
        "wizards/checks_to_date_view.xml",
        "reports/report_checks_to_date.xml",
        "security/ir.model.access.csv",
        # "data/arba_report.xml",
        # "data/account_return_data.xml",
        "data/sifere_report.xml",
        "data/sircar_report.xml",
        "data/sire_report.xml",
        "data/pba_report.xml",
        "data/caba_report.xml",
        "data/mendoza_report.xml",
        "data/misiones_report.xml",
        "data/santa_fe_report.xml",
        "data/tucuman_report.xml",
    ],
    "demo": [],
    "test": [],
    "installable": True,
    "auto_install": True,
    "application": False,
    "post_init_hook": "_post_init_hook_configure_ar_account_tags",
}
