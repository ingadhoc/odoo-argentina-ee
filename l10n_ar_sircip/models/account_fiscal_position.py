##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    def _check_tax_group_overlap_fp(self, fp_tax, partner, partner_tax, company, date):
        sircip_state = fp_tax._get_sircip_state()
        if fp_tax.default_tax_id.l10n_ar_state_id == sircip_state:
            # si el impuesto de la posicion fiscal es del mismo estado que sircip,
            # entonces no hay que validar nada porque permitimos que el grupo se haya overlap
            return
        super()._check_tax_group_overlap_fp(fp_tax, partner, partner_tax, company, date)

    def _needs_clean_up_0_taxes(self, partner_tax):
        # EXTEND l10n_ar_tax
        """Los impuestos SIRCIP en 0% no se descartan: aunque no se cobren, la operación se declara
        en la DDJJ (tipo de registro 2, informativo)."""
        if partner_tax and all(tax.tax_group_id.name == "SIRCIP" for tax in partner_tax):
            return False
        return super()._needs_clean_up_0_taxes(partner_tax)
