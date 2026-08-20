from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    settled_line_ids = fields.One2many(
        "account.move.line",
        "tax_settlement_move_id",
        "Settled Lines",
        # atencion, si sacamos el readonly por alguna razon, volver a agregarlo
        # en la vista porque si no da error al querer guardar cambios (probar
        # con usuario no admin pondiendo apuntes de liquidacion en cero)
        readonly=True,
        auto_join=True,
    )

    def download_tax_settlement_file(self):
        self.ensure_one()
        # para los que se liquidan desde reporte, no se encuentra el diario,
        # pero sabemos que es el diario donde se liquidaron
        return self.settled_line_ids.get_tax_settlement_file(self.journal_id)

    def unlink(self):
        """Protect entries already settled and recompute tax_state on settled lines.

        Deleting an entry whose tax lines are already included in a settlement silently
        drops them from that settlement: the settlement entry keeps its amount but loses
        the detail, and the tax lines re-created afterwards show up as pending again, so
        they end up settled (and declared) twice. Block it and let the user delete the
        settlement entry first, which is the operation that properly releases the lines.
        """
        settled_lines = self.line_ids.filtered("tax_settlement_move_id")
        if settled_lines:
            raise UserError(
                _(
                    "You can not delete an entry with tax lines already included in a tax settlement. "
                    "Delete the settlement entry first:\n%s",
                    "\n".join(
                        "* %s -> %s" % (line.move_id.display_name, line.tax_settlement_move_id.display_name)
                        for line in settled_lines
                    ),
                )
            )
        settlement_settled_lines = self.mapped("settled_line_ids")
        res = super().unlink()
        settlement_settled_lines._compute_tax_state()
        return res
