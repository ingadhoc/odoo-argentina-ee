{
    "name": "Tax settlement Mendoza",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "author": "ADHOC SA",
    "license": "LGPL-3",
    "depends": [
        "base_import_match",
        "l10n_ar_account_tax_settlement",
        "l10n_ar_tax_python",
        "l10n_ar_tax",
    ],
    "data": [
        "views/account_move_views.xml",
        "views/afip_activity_view.xml",
        "wizard/res_config_settings_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "post_init_hook": "post_init_hook",
}
