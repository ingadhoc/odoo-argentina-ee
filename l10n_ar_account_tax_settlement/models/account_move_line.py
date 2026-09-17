from odoo import _, models
from odoo.exceptions import UserError


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
        # unlink() runs on every journal item of the system, so the usual case has to leave right away
        lines = self.filtered(lambda x: x.tax_settlement_move_id and x.tax_line_id and x.payment_id)
        if not lines:
            return
        log = self.env["l10n_ar.unlinked.tax.settlement"].sudo()
        existing = {
            (record.move_id, record.tax_id): record
            for record in log.search([("move_id", "in", lines.move_id.ids), ("tax_id", "in", lines.tax_line_id.ids)])
        }
        # A dict per (entry, tax) also keeps two lines of the same batch from hitting uniq_move_tax
        to_create = {}
        for line in lines:
            key = (line.move_id, line.tax_line_id)
            if record := existing.get(key):
                record.settlement_move_id = line.tax_settlement_move_id
            else:
                to_create[key] = {
                    "move_id": line.move_id.id,
                    "tax_id": line.tax_line_id.id,
                    "settlement_move_id": line.tax_settlement_move_id.id,
                }
        if to_create:
            log.create(list(to_create.values()))

    def _get_unlinked_tax_settlement_log(self):
        self.ensure_one()
        return self.move_id.unlinked_tax_settlement_ids.filtered(lambda x: x.tax_id == self.tax_line_id)

    def _get_tax_settlement_to_reassign(self):
        """Best guess of the settlement this line should be linked back to, empty when we can not tell.

        What the entry kept is the reliable source. The gap is only a guess -it proves a settlement does
        not add up, not that this is the one missing- so it is offered in the wizard, never written on
        its own: withholding amounts repeat a lot and a wrong match balances the settlement in false.
        """
        self.ensure_one()
        if settlement := self._get_unlinked_tax_settlement_log().settlement_move_id:
            return settlement
        gaps = self._get_tax_settlement_gaps()
        exact = [move for move, gap in gaps.items() if self.company_currency_id.is_zero(gap + self.balance)]
        return exact[0] if len(exact) == 1 else self.env["account.move"]

    def _get_journal_tax_settlements(self, date_from=None):
        """Settlements posted in the journal that settles this line's tax, from ``date_from`` on.

        No filter on the company of the line: the settlement is born with the company of the journal,
        which ``_get_tax_settlement_journal`` looks up with ``parent_of``, so a branch settles its
        withholdings in the journal -and in the entry- of the parent company.
        """
        self.ensure_one()
        journal = self._get_tax_settlement_journal()
        if not journal:
            return self.env["account.move"]
        domain = [("journal_id", "=", journal.id), ("state", "=", "posted")]
        if date_from:
            domain.append(("date", ">=", date_from))
        return self.env["account.move"].search(domain, order="date desc, id desc")

    def _get_tax_settlement_gaps(self, settlements=None):
        """Settlements that no longer add up, with the amount each one is missing.

        A settlement books, per account, the counterpart of the lines it settles, so both add up to zero
        while those lines stay linked. A line that was settled and lost the link leaves the settlement
        with a gap of exactly its own balance.
        """
        self.ensure_one()
        if settlements is None:
            # A settlement is never older than the line it settles, which is what bounds the search
            settlements = self._get_journal_tax_settlements(date_from=self.date)
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

    def _get_tax_settlement_reassign_candidates(self, settlements=None):
        """Settlements suggested to the user: the ones left with a gap, or all of them when none shows one."""
        self.ensure_one()
        if settlements is None:
            settlements = self._get_journal_tax_settlements(date_from=self.date)
        gaps = self._get_tax_settlement_gaps(settlements)
        return self.env["account.move"].union(*gaps) if gaps else settlements

    def _check_tax_settlement_gap(self, settlement):
        """Refuse to link lines back to a settlement that is not missing exactly their amount.

        Restoring the link does not fix a settlement that is missing another amount: if the withholding
        was edited to a different one, it would keep declaring what nobody withheld, and if it was
        already corrected by hand, the amount would end up declared twice. Amounts are compared per
        account, which is how the settlement books them.
        """
        for account, lines in self.grouped("account_id").items():
            gap = lines[0]._get_tax_settlement_gaps(settlement).get(settlement, 0.0)
            if not lines[0].company_currency_id.is_zero(gap + sum(lines.mapped("balance"))):
                raise UserError(
                    _(
                        "Settlement %(settlement)s is not missing the amount of the withholdings you are "
                        "reassigning to it, on account %(account)s. The amount may have changed when the "
                        "payment was edited, or the settlement may have been corrected by hand. Review the "
                        "settlement before linking them back.",
                        settlement=settlement.display_name,
                        account=account.display_name,
                    )
                )

    def reassign_tax_settlement(self, settlement):
        """Link these lines back to a settlement and forget what we had kept for them."""
        self._check_tax_settlement_gap(settlement)
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
