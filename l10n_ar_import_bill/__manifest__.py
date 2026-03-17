{
    "name": "Argentinian Importing Bills from ARCA",
<<<<<<< 587ebe5f913ea55075a92c12d8e47fa36cadb003
    "version": "19.0.1.2.0",
||||||| 3c937bcace0de216f0ecac1d2b54593b2dc70bd5
    "version": "18.0.1.2.0",
=======
    "version": "18.0.1.3.0",
>>>>>>> bb40a80a4f54a326b30aec11ad58b5022384f44e
    "category": "Localization/Argentina",
    "sequence": 8,
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "AGPL-3",
    "summary": "",
    "depends": ["account_accountant", "l10n_ar_edi", "account_invoice_tax", "account_balance_import"],
    "data": [
        "security/ir.model.access.csv",
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
