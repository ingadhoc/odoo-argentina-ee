from odoo import _, models

# How many settlements of the journal we look back at when guessing where a withholding was declared
SETTLEMENT_SEARCH_LIMIT = 40


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_settlement_tax(self, date=None):
        """Método puente para poder usar l10n_ar_tax_settlement_backward_comp
        Deprecar este método cuando se deprecie con l10n_ar_tax_settlement_backward_comp.
        El parámetro date es porque si la base no tiene instalado l10n_ar_tax_settlement_backward_comp
        entonces va a arrojar error si en alguna llamada al método se le pasa date.
        Ejemplo: método iibb_aplicado_agip_files_values de account_tax en módulo
        l10n_ar_account_tax_settlement hace la llamada tax = line._get_settlement_tax(date=date)"""
        self.ensure_one()
        return self.tax_line_id

    def unlink(self):
        """Remember the settlement of a payment withholding before dropping its journal item.

        Editing a payment in draft makes l10n_ar_withholding delete the withholding journal items and
        the synchronization re-create them. The new ones are born without ``tax_settlement_move_id``, so
        a withholding already declared shows up as pending to settle again, with nothing warning the user.
        We keep what was lost on the entry, which survives the whole edit cycle, to be able to restore it.
        """
        self._log_unlinked_tax_settlements()
        return super().unlink()

    def _log_unlinked_tax_settlements(self):
        log = self.env["l10n_ar.unlinked.tax.settlement"].sudo()
        for line in self.filtered(lambda x: x.tax_settlement_move_id and x.tax_line_id and x.payment_id):
            existing = log.search([("move_id", "=", line.move_id.id), ("tax_id", "=", line.tax_line_id.id)], limit=1)
            if existing:
                existing.settlement_move_id = line.tax_settlement_move_id
            else:
                log.create(
                    {
                        "move_id": line.move_id.id,
                        "tax_id": line.tax_line_id.id,
                        "settlement_move_id": line.tax_settlement_move_id.id,
                    }
                )

    def _get_unlinked_tax_settlement_log(self):
        self.ensure_one()
        return self.move_id.unlinked_tax_settlement_ids.filtered(lambda x: x.tax_id == self.tax_line_id)

    def _get_tax_settlement_to_reassign(self):
        """Settlement this line should be linked back to, or an empty recordset when we can not tell.

        What the entry kept is the reliable source. We only guess when there is nothing kept -lines broken
        before this module was installed- and a single settlement is left with a gap of exactly this amount.
        """
        self.ensure_one()
        if settlement := self._get_unlinked_tax_settlement_log().settlement_move_id:
            return settlement
        gaps = self._get_tax_settlement_gaps()
        exact = [move for move, gap in gaps.items() if self.company_currency_id.is_zero(gap + self.balance)]
        return exact[0] if len(exact) == 1 else self.env["account.move"]

    def _get_journal_tax_settlements(self):
        """Last settlements posted in the journal that settles this line's tax."""
        self.ensure_one()
        journal = self._get_tax_settlement_journal()
        if not journal:
            return self.env["account.move"]
        return self.env["account.move"].search(
            [("journal_id", "=", journal.id), ("company_id", "=", self.company_id.id), ("state", "=", "posted")],
            order="date desc, id desc",
            limit=SETTLEMENT_SEARCH_LIMIT,
        )

    def _get_tax_settlement_gaps(self, settlements=None):
        """Settlements that no longer add up, with the amount each one is missing.

        A settlement books, per account, the counterpart of the lines it settles, so both add up to zero
        while those lines stay linked. A line that was settled and lost the link leaves the settlement
        with a gap of exactly its own balance.
        """
        self.ensure_one()
        if settlements is None:
            settlements = self._get_journal_tax_settlements()
        gaps = {}
        # A settlement that lost its only settled line has no settled_line_ids left, so it can not be
        # filtered out by them: the journal is what tells the entries apart.
        for settlement in settlements:
            same_account = settlement.line_ids.filtered(lambda x: x.account_id == self.account_id)
            settled = settlement.settled_line_ids.filtered(lambda x: x.account_id == self.account_id)
            gap = sum(same_account.mapped("balance")) + sum(settled.mapped("balance"))
            if not self.company_currency_id.is_zero(gap):
                gaps[settlement] = gap
        return gaps

    def _get_tax_settlement_reassign_candidates(self):
        """Settlements offered to the user: the ones left with a gap, or all of them when none shows one."""
        self.ensure_one()
        settlements = self._get_journal_tax_settlements()
        gaps = self._get_tax_settlement_gaps(settlements)
        return self.env["account.move"].union(*gaps) if gaps else settlements

    def reassign_tax_settlement(self, settlement):
        """Link these lines back to a settlement and forget what we had kept for them."""
        self.tax_settlement_move_id = settlement
        for line in self:
            line._get_unlinked_tax_settlement_log().sudo().unlink()
        return self._get_tax_settlement_reassign_notification()

    def action_reassign_tax_settlement(self):
        """Ask the user for the settlement of the lines we could not identify on our own."""
        return {
            "name": _("Reassign Tax Settlement"),
            "type": "ir.actions.act_window",
            "res_model": "l10n_ar.tax.settlement.reassign",
            "view_mode": "form",
            "target": "new",
            "context": {"default_line_ids": self.ids},
        }

    def _get_tax_settlement_reassign_notification(self):
        """Confirm which settlement each withholding ended up in, the data the user came for."""
        settlements = ", ".join(sorted(set(self.mapped("tax_settlement_move_id.display_name"))))
        message = (
            _("The withholding was reassigned to %s.", settlements)
            if len(self) == 1
            else _("The withholdings were reassigned to %s.", settlements)
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": "success", "next": {"type": "ir.actions.act_window_close"}},
        }
