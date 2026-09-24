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

    def needs_clean_up_0_taxes(self, partner_tax):
        # EXTEND l10n_ar_tax
        """Checks that the conditions were we do not need to clean up 0 amount taxes

        - case 2: SIRCIP. We do not want it to remove the 0 taxes

        NOTE: We leave it as a separete method in case we want to add more cases
        in the future and make it inheritable by other modules"""
        sircip_state = self.env["account.fiscal.position.l10n_ar_tax"]._get_sircip_state()
        if len(partner_tax) > 1 and partner_tax[0].l10n_ar_state_id == sircip_state:
            return False
        super().needs_clean_up_0_taxes(partner_tax)
