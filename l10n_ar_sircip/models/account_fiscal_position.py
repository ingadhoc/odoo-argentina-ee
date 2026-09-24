##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    l10n_ar_sircip_warning = fields.Text(string="SIRCIP Warning", compute="_compute_l10n_ar_sircip_warning")

    @api.depends("company_id.l10n_ar_sircip_agent", "l10n_ar_tax_ids.default_tax_id", "l10n_ar_tax_ids.tax_type")
    def _compute_l10n_ar_sircip_warning(self):
        """Avisos para compañías agentes: posición fiscal con percepciones pero sin la línea SIRCIP, o con percepciones
        de provincias que ya pasaron a SIRCIP (esas líneas hay que sacarlas)."""
        for rec in self:
            messages = []
            perceptions = rec.l10n_ar_tax_ids.filtered(lambda x: x.tax_type == "perception")
            if rec.company_id.l10n_ar_sircip_agent and perceptions:
                sircip = perceptions.filtered(lambda x: x._l10n_ar_is_sircip())
                if not sircip:
                    messages.append(
                        self.env._(
                            "This fiscal position has perceptions but not the SIRCIP line. Save the Accounting "
                            "settings with 'SIRCIP Perception Agent' checked to add it."
                        )
                    )
                adhered = (perceptions - sircip).default_tax_id.l10n_ar_state_id.filtered("l10n_ar_is_sircip")
                if adhered:
                    messages.append(
                        self.env._(
                            "Perceptions of provinces adhered to SIRCIP: %(states)s. They are now collected through "
                            "SIRCIP, remove those lines.",
                            states=", ".join(adhered.mapped("name")),
                        )
                    )
            rec.l10n_ar_sircip_warning = "\n".join(messages)

    def _l10n_ar_get_fp_tax_taxes(self, fp_tax, partner, company, date, tax_type, payment=None):
        # EXTEND l10n_ar_tax
        """La línea SIRCIP se calcula en cada factura y no desde los impuestos guardados en el partner:
        el resultado depende de la provincia de entrega y puede ser más de un impuesto (sobretasa)."""
        if tax_type == "perception" and fp_tax._l10n_ar_is_sircip():
            return fp_tax._sircip_get_taxes(partner, date)
        return super()._l10n_ar_get_fp_tax_taxes(fp_tax, partner, company, date, tax_type, payment=payment)
