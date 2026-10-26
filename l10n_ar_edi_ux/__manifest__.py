{
    "name": "Argentinian Electronic Invoicing UX",
    "version": "20.0.1.0.0",
    "category": "Localization/Argentina",
    "sequence": 14,
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "LGPL-3",
    "summary": "",
    "depends": [
        "account_ux",  # shared_to_branches, que este asistente escribe en el diario que crea
        "l10n_ar_ux",
        "contacts",  # its menu hosts the padron wizard; came through l10n_latam_base up to 19.0
        "l10n_ar_edi",
        "account_accountant",
        "account_base_import",
    ],
    "data": [
        "wizards/res_partner_update_from_padron_wizard_view.xml",
        "wizards/l10n_ar_arca_connection_wizard_view.xml",
        "wizards/l10n_ar_arca_journal_wizard_view.xml",
        "views/certificate_certificate_view.xml",
        "views/res_partner_view.xml",
        "views/account_move_view.xml",
        "views/account_journal_view.xml",
        "views/res_config_settings_view.xml",
        "views/l10n_ar_boarding_permission_view.xml",
        "views/report_invoice.xml",
        "security/ir.access.csv",
    ],
    "demo": [
        "demo/res_partner_demo.xml",
    ],
    "installable": True,
    "auto_install": True,
    "application": False,
    "post_init_hook": "post_init_hook",
    "post_load": "monkey_patches",
}
