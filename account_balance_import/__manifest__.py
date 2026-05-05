{
    "name": "Account Balance",
    "version": "19.0.1.7.0",
    "category": "Planner",
    "sequence": 14,
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "AGPL-3",
    "summary": "Provides a wizard for importing initial account balances",
    "depends": [
        "account_ux",
        "account_base_import",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_onboarding_views.xml",
        "wizards/account_balance_import_wizard.xml",
        "views/account_account_views.xml",
        "views/res_config_settings_views.xml",
        "views/account_journal_dashboard_view.xml",
        "views/account_import_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "account_balance_import/static/src/js/**/*",
            "account_balance_import/static/src/xml/**/*",
        ],
    },
    "installable": True,
}
