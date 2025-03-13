from odoo.addons.l10n_ar_reports.report.account_ar_vat_line import AccountArVatLine


def _revert_method(cls, name):
    """Revertir el método original llamado 'name'"""
    method = getattr(cls, name)
    setattr(cls, name, method.origin)


def uninstall_hook(cr, registry):
    _revert_method(AccountArVatLine, "_ar_vat_line_build_query")
