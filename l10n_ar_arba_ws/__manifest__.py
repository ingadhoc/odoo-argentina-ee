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
    "name": "ARBA Webservice (A122R)",
    "version": "18.0.1.6.0",
    "category": "Localization/Argentina",
    "sequence": 14,
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "AGPL-3",
    "summary": "",
    "depends": [
        "l10n_ar_tax",
        "l10n_ar_edi",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/l10n_ar_dj_arba_views.xml",
        "views/account_payment_views.xml",
        "views/res_config_settings_views.xml",
        "views/l10n_ar_payment_withholding_views.xml",
        "wizard/arba_withholding_draft_warning_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
