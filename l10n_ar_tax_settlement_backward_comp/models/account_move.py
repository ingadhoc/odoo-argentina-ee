from odoo import Command, _, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def copy(self, default=None):
        res = super().copy(default=default)
        # para facturas que se duplican y:
        # a) venian de la versión anterior
        # b) y no tenian fp o la fp no tenía "percepciones argentinas"
        # c) tiene impuestos con "is_backward_tax" archivados
        # re-calculamos pa percepción desde partner tax
        for rec, new_move in zip(self, res):
            if not (rec.is_sale_document() and rec.country_code == "AR"):
                continue
            # account_ux already removed archived taxes from the copy, so we read them from the original lines
            if len(rec.invoice_line_ids) != len(new_move.invoice_line_ids):
                continue
            lines_pairs = list(zip(rec.invoice_line_ids, new_move.invoice_line_ids))
            # tax commands per new line, written once per move to avoid one tax sync per line
            line_commands = {}
            backward_taxes = rec.line_ids.mapped("tax_line_id").filtered("is_backward_tax")
            for bw_tax in backward_taxes:
                if bw_tax.active:
                    # if its active then is created in new version, so we skip it
                    continue

                partner = rec.commercial_partner_id
                tax_line = rec.line_ids.filtered(lambda l: l.tax_line_id == bw_tax)[:1]
                new_lines = [new_line for line, new_line in lines_pairs if bw_tax in line.tax_ids]

                if partner_tax := partner.l10n_ar_partner_perception_ids.filtered(
                    lambda x: x.company_id == tax_line.company_id
                    and x.tax_id.l10n_ar_state_id == tax_line.tax_line_id.l10n_ar_state_id
                    and (x.from_date <= tax_line.date if x.from_date else not x.from_date)
                    and (x.to_date >= tax_line.date if x.to_date else not x.to_date)
                ):
                    # partner taxes can't overlap within a tax group, so several matches belong to different
                    # groups of the same state: prefer the backward tax group
                    partner_tax = (
                        partner_tax.filtered(lambda x: x.tax_id.tax_group_id == bw_tax.tax_group_id) or partner_tax
                    )
                    new_tax = partner_tax[:1].tax_id
                    for line in new_lines:
                        # remove backward tax and add partner tax
                        commands = line_commands.setdefault(line, [])
                        commands.append(Command.unlink(bw_tax.id))
                        # skip it if the fiscal position already added a perception of the same group
                        if new_tax.tax_group_id not in (line.tax_ids - bw_tax).tax_group_id:
                            commands.append(Command.link(new_tax.id))
                else:
                    for line in new_lines:
                        # just remove backward tax
                        line_commands.setdefault(line, []).append(Command.unlink(bw_tax.id))
                    new_move.message_post(
                        body=_(
                            "The backward tax '%(tax_name)s (id: %(tax_id)s)' was removed from the copied move "
                            "because there is no corresponding partner tax configured."
                        )
                        % {"tax_name": bw_tax.name, "tax_id": bw_tax.id},
                    )
            if line_commands:
                new_move.write(
                    {
                        "invoice_line_ids": [
                            Command.update(line.id, {"tax_ids": commands}) for line, commands in line_commands.items()
                        ]
                    }
                )

        return res
