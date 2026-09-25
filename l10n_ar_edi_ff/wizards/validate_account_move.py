from odoo import Command, models


class ValidateAccountMove(models.TransientModel):
    _inherit = "validate.account.move"

    def validate_move(self):
        """account_background_post validates the selected invoices one by one, so a batch never gets more than
        one invoice. Validate the invoices of batch journals with a single action_post; the rest keeps the
        one-by-one loop."""
        batch = self.move_ids.filtered(lambda m: m.state == "draft" and m.journal_id.l10n_ar_batch_cae)
        if not self.count_inv or not batch or self.count_inv > self.batch_size:
            return super().validate_move()
        batch.action_post()
        self.env.cr.commit()  # pragma pylint: disable=invalid-commit
        rest = self.move_ids - batch
        if not rest:
            return {"type": "ir.actions.act_window_close"}
        self.write({"move_ids": [Command.set(rest.ids)], "count_inv": len(rest)})
        return super().validate_move()
