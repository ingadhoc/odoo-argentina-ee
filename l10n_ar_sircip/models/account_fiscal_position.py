##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    def _l10n_ar_get_fp_tax_taxes(self, fp_tax, partner, company, date, tax_type, payment=None):
        # EXTEND l10n_ar_tax
        """La línea SIRCIP se calcula en cada factura y no desde los impuestos guardados en el partner:
        el resultado depende de la provincia de entrega y puede ser más de un impuesto (sobretasa)."""
        if tax_type == "perception" and fp_tax._l10n_ar_is_sircip():
            return fp_tax._sircip_get_taxes(partner, date)
        return super()._l10n_ar_get_fp_tax_taxes(fp_tax, partner, company, date, tax_type, payment=payment)
