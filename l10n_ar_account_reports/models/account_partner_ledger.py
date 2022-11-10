from odoo import models, api


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'


    @api.model
    def _get_report_line_partners(self, options, partner, partner_values):
        """ We extend this method in order to show more information aside the partner's name: we add the
        identification type name and the related document number:

        * before the partner was shown as "Partner Name"
        * with this method now will be shown as "Partner Name (CUIT: 1234234235)"
        """
        res = super()._get_report_line_partners(
            options=options, partner=partner,partner_values=partner_values)
        partner_name = res.get("name")
        if partner and partner.l10n_latam_identification_type_id.name and partner.vat:
            doc_info = partner.l10n_latam_identification_type_id.name + ": " + partner.vat
            res.update({"name": partner_name[:128 - len(doc_info) - 3] + " (%s)" % doc_info})

        return res
