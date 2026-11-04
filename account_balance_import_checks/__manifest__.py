{
    "name": "Account Balance Import - Checks",
    "version": "20.0.1.0.0",
    "category": "Accounting",
    "sequence": 14,
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "LGPL-3",
    "summary": "Import checks with initial balances using account_balance_import",
    "depends": [
        "l10n_latam_check",
        "account_balance_import",
        "l10n_latam_check_ux",
    ],
    "data": [
        "wizard/account_balance_import_checks_wizard.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "account_balance_import_checks/static/src/js/**/*",
            "account_balance_import_checks/static/src/xml/**/*",
        ],
    },
    "installable": True,
    "auto_install": True,
}
