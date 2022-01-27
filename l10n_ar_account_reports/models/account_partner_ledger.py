from odoo import models, api


class ReportPartnerLedger(models.AbstractModel):
    _inherit = 'account.partner.ledger'


    @api.model
    def _get_report_line_partner(self, options, partner, initial_balance, debit, credit, balance):
        """ We extend this method in order to show more information aside the partner's name: we add the
        identification type name and the related document number:

        * before the partner was shown as "Partner Name"
        * with this method now will be shown as "Partner Name (CUIT: 1234234235)"
        """
        res = super()._get_report_line_partner(
            options=options, partner=partner, initial_balance=initial_balance, debit=debit, credit=credit, balance=balance)
        partner_name = res.get("name")
        if partner and partner.l10n_latam_identification_type_id.name and partner.vat:
            doc_info = partner.l10n_latam_identification_type_id.name + ": " + partner.vat
            res.update({"name": partner_name[:128 - len(doc_info) - 3] + " (%s)" % doc_info})

        return res
