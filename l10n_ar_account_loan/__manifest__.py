{
    "name": "Argentinian Loans",
    "version": "19.0.1.0.0",
    "category": "Localization/Argentina",
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "AGPL-3",
    "summary": "Register taken loans (disbursement, monthly bills with taxes and standard payment) the Argentinian way",
    "depends": [
        "account_loans",
        "l10n_ar",
        "account_invoice_tax",
    ],
    "data": [
        "views/account_loan_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
