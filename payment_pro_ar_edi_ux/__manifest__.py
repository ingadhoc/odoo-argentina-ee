# © 2025 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Account Payment pro for l10n_ar_edi",
    "version": "17.0.1.0.0",
    "category": "Payment",
    "website": "www.adhoc.com.ar",
    "author": "ADHOC SA",
    "license": "AGPL-3",
    'installable': True,
    "external_dependencies": {
        "python": [],
        "bin": [],
    },
    "depends": [
        "account_payment_pro",
        "l10n_ar_edi_ux",
    ],
    "data": [
        "wizards/account_payment_invoice_wizard_view.xml",
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    "demo": [
    ],
}
