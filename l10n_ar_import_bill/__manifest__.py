{
    "name": "Argentinian Importing Bills from ARCA",
    "version": "20.0.1.0.0",
    "category": "Localization/Argentina",
    "sequence": 8,
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "LGPL-3",
    "summary": "",
    "depends": ["account_accountant", "l10n_ar_edi", "account_invoice_tax", "account_balance_import"],
    "data": [
        "security/ir.access.csv",
        "wizards/afip_import_wizard.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ar_import_bill/static/src/js/**/*",
            "l10n_ar_import_bill/static/src/xml/**/*",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
