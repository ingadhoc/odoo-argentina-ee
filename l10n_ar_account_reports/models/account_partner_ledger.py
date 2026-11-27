from odoo import models


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = "account.partner.ledger.report.handler"

    def _get_custom_groupby_map(self):
        """Show the partner's identification next to its name in the partner ledger.

        * without this, the partner is shown as "Partner Name"
        * with it, as "Partner Name (CUIT: 1234234235)"

        In 19 this hooked ``_get_report_line_partners``, which 20.0 removed when the
        report was rewritten: the label of each partner group now comes from the
        ``label_builder`` of this map.
        """
        groupby_map = super()._get_custom_groupby_map()
        partner_groupby = groupby_map.get("partner_id")
        if not partner_groupby:
            return groupby_map

        native_label_builder = partner_groupby["label_builder"]

        def label_builder(ids):
            labels = native_label_builder(ids)
            for partner in self.env["res.partner"].browse([_id for _id in ids if _id]):
                doc_info = self._l10n_ar_partner_doc_info(partner)
                name = labels.get(partner.id)
                if doc_info and name:
                    labels[partner.id] = f"{name[: 128 - len(doc_info) - 3]} ({doc_info})"
            return labels

        groupby_map["partner_id"] = {**partner_groupby, "label_builder": label_builder}
        return groupby_map

    def _l10n_ar_partner_doc_info(self, partner):
        """ "CUIT: 30710158254" for the identifier the partner is identified with, or ""."""
        vals = partner._get_preferred_legal_entity_identifier_vals()
        if not vals or not vals.get("value"):
            return ""
        label = vals.get("label") or vals["key"].removeprefix("AR_")
        return f"{label}: {vals['value']}"
