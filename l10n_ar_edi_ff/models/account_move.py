import logging

from odoo import api, models
from odoo.exceptions import UserError

from ..patch import ERRORS_KEY, _enabled

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _cron_background_post_invoices(self, ids=None):
        """Post the due invoices in chunks of `account_background_post.batch_size`, one action_post per chunk,
        so wsfe invoices reach ARCA in a single request instead of one by one."""
        if not _enabled(self.env):
            return super()._cron_background_post_invoices(ids=ids)
        moves = self.browse(ids) if ids is not None else self._get_background_post_due_moves()
        # ARCA rejects a date older than the last authorized one: oldest first, immediate before scheduled.
        moves = moves.sorted(lambda m: (bool(m.background_post_date), m.invoice_date or m.date, m.id))
        size = max(1, self._get_background_post_batch_size())
        cron = self.env["ir.cron"]
        remaining_time = cron._commit_progress(remaining=len(moves))
        for start in range(0, len(moves), size):
            if remaining_time <= 0:
                _logger.info(
                    "Background post cron ran out of time, %s invoices left for the next run", len(moves) - start
                )
                break
            chunk = moves[start : start + size]
            self.env.cr.cache[ERRORS_KEY] = {}
            try:
                chunk.with_context(ff_collect_errors=True).action_post()
            except Exception as exp:  # noqa: BLE001
                # Not an ARCA rejection (those are collected): retry what is left one by one.
                self.env.cr.rollback()
                _logger.warning("Background post chunk failed, retrying one by one: %s", exp)
                for move in chunk.filtered(lambda m: m.state == "draft"):
                    try:
                        move.action_post()
                    except Exception as move_exp:  # noqa: BLE001
                        self.env.cr.rollback()
                        self.env.cr.cache[ERRORS_KEY][move.id] = move_exp
            errors = self.env.cr.cache.pop(ERRORS_KEY, {})
            for move in self.browse(list(errors)):
                error = errors[move.id]
                move._ff_background_post_failed(error if isinstance(error, Exception) else UserError(error))
            remaining_time = cron._commit_progress(processed=len(chunk))

    def _ff_background_post_failed(self, error):
        """Same handling as a failure in the original cron: reschedule, or give up and notify."""
        self.ensure_one()
        if self._reschedule_background_post():
            _logger.warning(
                "Error while trying to post invoice %s in background, retry %s scheduled for %s: %s",
                self.id,
                self.background_post_attempts,
                self.background_post_date,
                error,
            )
            return
        self._unschedule_background_post()
        try:
            with self.env.cr.savepoint():
                self._notify_background_post_error(error)
        except Exception:
            _logger.exception("Could not notify the background post error of invoice %s", self.id)
        _logger.error("Error while trying to post invoice %s in background: %s", self.id, error)
