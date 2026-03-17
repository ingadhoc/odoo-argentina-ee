{
    "name": "Argentinian Importing Bills from ARCA",
    "version": "18.0.1.3.0",
    "category": "Localization/Argentina",
    "sequence": 8,
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "AGPL-3",
    "summary": "",
    "depends": ["account_accountant", "l10n_ar_edi", "account_invoice_tax"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/afip_import_wizard.xml",
        "views/account_move.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
