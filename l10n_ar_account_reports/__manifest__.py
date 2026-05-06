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
    "version": "19.0.1.17.0",
    "category": "Accounting",
    "sequence": 14,
    "summary": "",
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "AGPL-3",
    "images": [],
    "depends": [
        "accountant",  # en si este modulo no es necesario pero de alguna manera este modulo solo tiene sentido para
        # bases que usan contabilida (tienen accountant)
        "account_reports",
        "l10n_ar",
        "l10n_ar_tax",
        "l10n_ar_withholding",
        "l10n_latam_check",
        "l10n_ar_reports",
        # necesitamos talonario de recibo para que los pagos
        # salgan con formato correcto, ejemplo: OP-X 0001-00000001
        # ya que esto es requerido en la descarga de algunos txt de impuestos
        "account_payment_pro_receiptbook",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_return_type_views.xml",
        "views/inflation_adjustment_index_view.xml",
        "data/tags_data.xml",
        "data/estado_resultados.xml",
        "data/balance_sheet.xml",
        "data/sifere_report.xml",
        "data/sircar_report.xml",
        "data/pba_report.xml",
        "data/caba_report.xml",
        "data/l10n_ar_vat_ret_perc_sufrido.xml",
        "data/mendoza_report.xml",
        "data/misiones_report.xml",
        "data/santa_fe_report.xml",
        "data/tucuman_report.xml",
        "data/sicore_report.xml",
        "data/inflation_adjustment_index.xml",
        "data/account_report_settlement.xml",
        "wizard/inflation_adjustment_view.xml",
    ],
    "demo": [
        "demo/res_partner_demo.xml",
        "demo/account_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ar_account_reports/static/src/**/*",
        ],
    },
    "test": [],
    "installable": True,
    "auto_install": ["l10n_ar"],
    "application": False,
    "post_init_hook": "_post_init_hook_configure_ar_account_tags",
}
