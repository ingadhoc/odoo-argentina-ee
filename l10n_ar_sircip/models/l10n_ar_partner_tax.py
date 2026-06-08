##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models


class L10nArPartnerTax(models.Model):
    _inherit = "l10n_ar.partner.tax"

    @api.constrains("partner_id", "tax_id", "from_date", "to_date")
    def _check_tax_group_overlap(self):
        # Para SIRCIP se permite tener múltiples registros del mismo grupo en el mismo
        # período porque un contacto padre puede tener hijos (direcciones de entrega)
        # en distintas provincias adheridas, cada una con su propia alícuota.
        sircip_group = self.env.ref("l10n_ar_sircip.tax_group_sircip", raise_if_not_found=False)
        if sircip_group:
            non_sircip = self.filtered(lambda r: r.tax_id.tax_group_id != sircip_group)
        else:
            non_sircip = self
        return super(L10nArPartnerTax, non_sircip)._check_tax_group_overlap()
