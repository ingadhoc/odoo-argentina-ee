import logging
import time
from datetime import datetime

from markupsafe import Markup
from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import SQL, plaintext2html
from psycopg2 import errors as pg_errors

_logger = logging.getLogger(__name__)

PARAM = "l10n_ar_edi_ff"
ERRORS_KEY = f"{PARAM}.errors"


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # Posting
    # -------------------------------------------------------------------------

    def _ff_is_batchable(self):
        self.ensure_one()
        return (
            self.journal_id.l10n_ar_batch_cae
            and self.journal_id.l10n_ar_afip_ws == "wsfe"
            and self.is_invoice()
            and self.country_code == "AR"
            and self.move_type in ("out_invoice", "out_refund")
            and not self.l10n_ar_afip_auth_code
            and not self._is_dummy_afip_validation()
        )

    def _post(self, soft=True):
        # Inside a batch every invoice goes through the regular chain one by one: do not batch again.
        if self.env.context.get("l10n_ar_batch_ids"):
            return super()._post(soft=soft)
        batchable = self.filtered(lambda m: m._ff_is_batchable())
        if not batchable:
            return super()._post(soft=soft)

        rest = self - batchable
        validated = super(AccountMove, rest)._post(soft=soft) if rest else self.browse()
        size = max(1, int(self.env["ir.config_parameter"].sudo().get_param(f"{PARAM}.batch_size", 20)))
        failed = {}

        groups = {}
        for inv in batchable.sorted(lambda m: (m.invoice_date or m.date, m.id)):
            key = (inv.company_id.id, inv.journal_id.id, inv.l10n_latam_document_type_id.id)
            groups.setdefault(key, []).append(inv.id)
        for queue in groups.values():
            while queue:
                chunk = self.browse(queue[:size])
                done, chunk_failed, pending = chunk._ff_post_chunk(soft)
                validated |= done
                failed.update(chunk_failed)
                queue = pending.ids + queue[size:]

        if failed and self.env.context.get("l10n_ar_batch_collect_errors"):
            # The background post cron handles each failure on its own. Not a dict in the context: Odoo reuses
            # environments whose context compares equal, so an empty dict would be shared between calls.
            self.env.cr.cache.setdefault(ERRORS_KEY, {}).update({inv.id: msg for inv, msg in failed.items()})
        elif failed:
            lines = "\n\n".join(
                self.env._("* %(inv)s (id %(id)s):\n%(msg)s", inv=inv.display_name, id=inv.id, msg=msg)
                for inv, msg in failed.items()
            )
            if validated:
                raise UserError(
                    self.env._(
                        "These documents were validated in ARCA:\n   * %(ok)s\n\nThese documents were not:\n%(ko)s",
                        ok="\n   * ".join(validated.mapped("name")),
                        ko=lines,
                    )
                )
            raise UserError(self.env._("We couldn't validate the documents in ARCA:\n%s", lines))
        return validated

    def _l10n_ar_do_afip_ws_request_cae(self, client, auth, transport):
        """The invoices of the current batch are posted without CAE: the batch requests it for all of them."""
        batch_ids = self.env.context.get("l10n_ar_batch_ids") or ()
        others = self.filtered(lambda m: m.id not in batch_ids)
        if others:
            return super(AccountMove, others)._l10n_ar_do_afip_ws_request_cae(client, auth, transport)
        return False

    # -------------------------------------------------------------------------
    # Batch
    # -------------------------------------------------------------------------

    def _ff_lock(self):
        """Serialize CAE requests per (company, journal, document type).

        The transaction lock is released by the commit at the end of each chunk.
        """
        inv = self[0]
        key = f"{PARAM}:{inv.company_id.id}:{inv.journal_id.id}:{inv.l10n_latam_document_type_id.id}"
        cr = self.env.cr
        timeout = self.env["ir.config_parameter"].sudo().get_param(f"{PARAM}.lock_timeout", "10s")
        cr.execute("SET LOCAL lock_timeout = %s", [timeout])
        try:
            with cr.savepoint(flush=False):
                cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [key])
        except pg_errors.LockNotAvailable:
            raise UserError(
                self.env._(
                    "Another process is validating %(doc)s documents on journal %(journal)s. Try again in a moment.",
                    doc=inv.l10n_latam_document_type_id.display_name,
                    journal=inv.journal_id.display_name,
                )
            ) from None
        finally:
            cr.execute("SET LOCAL lock_timeout = DEFAULT")

    def _ff_send(self, client, auth, request):
        """Isolated so tests can simulate a lost response."""
        return client.service.FECAESolicitar(auth, request)

    def _ff_recover(self, details, client, auth):
        """Find out which documents of the chunk ARCA registered although we got no usable answer.

        Returns (values to write for the registered prefix of the chunk, last number authorized in ARCA).
        Stops at the first document that is not registered (or does not match), because ARCA authorizes in
        order.
        """
        journal = self[0].journal_id
        doc_type = self[0].l10n_latam_document_type_id
        last = journal._l10n_ar_get_afip_last_invoice_number(doc_type)
        recovered = []
        for inv, detail in zip(self, details):
            if detail["CbteDesde"] > last:
                break
            res = client.service.FECompConsultar(
                auth,
                {
                    "CbteTipo": doc_type.code,
                    "CbteNro": detail["CbteDesde"],
                    "PtoVta": journal.l10n_ar_afip_pos_number,
                },
            )
            got = res.ResultGet
            if (
                res.Errors
                or not got
                or (
                    got.CbteFch != detail["CbteFch"]
                    or float(got.ImpTotal) != float(detail["ImpTotal"])
                    or int(got.DocNro) != int(detail["DocNro"])
                )
            ):
                _logger.warning("ff: %s number %s in ARCA does not match, stop recovery", inv.id, detail["CbteDesde"])
                break
            recovered.append(
                {
                    "l10n_ar_afip_auth_mode": got.EmisionTipo,
                    "l10n_ar_afip_auth_code": str(got.CodAutorizacion),
                    "l10n_ar_afip_auth_code_due": datetime.strptime(got.FchVto, "%Y%m%d").date(),
                    "l10n_ar_afip_result": got.Resultado,
                }
            )
        _logger.info("ff: recovered %s of %s documents from ARCA (last %s)", len(recovered), len(self), last)
        return recovered, last

    def _ff_unrecovered_msg(self, lost, response, codes, number, last):
        """Error for a document that ARCA did not register: what ARCA said (or that it did not answer),
        plus both numbers, so a numbering mismatch is obvious."""
        self.ensure_one()
        if lost is not None:
            msg = self.env._("No answer from ARCA: %s", repr(lost))
        else:
            errors = "".join(f"\n* Code {e.Code}: {e.Msg}" for e in response.Errors.Err)
            # Same split as l10n_ar_edi autofix, so the hint fits: 10016-1 is the date, 10016-2 the numbering.
            kind = "10016-1" if number == last + 1 else "10016-2"
            msg = self._prepare_return_msg("wsfe", errors, "", "", [kind if c == "10016" else c for c in codes])
        return (
            msg
            + "\n\n"
            + self.env._(
                "Number sent by Odoo: %(odoo)s. Last number authorized in ARCA: %(arca)s.", odoo=number, arca=last
            )
        )

    def _ff_reject_from(self, index, msg, retry, numbering, xml_values):
        """The document at `index` of this posted chunk was rejected (its posting is already rolled back).

        Returns ({invoice: error message}, pending): ARCA only evaluated the rejected one, so the rest are
        retried, unless retrying is pointless (no answer, header error, numbering mismatch).
        """
        rejected = self[index]
        rest = self[index + 1 :]
        failed = {rejected: msg or self.env._("Rejected by ARCA")}
        if retry:
            pending = rest
        else:
            pending = self.browse()
            rest_msg = msg
            if numbering:
                rest_msg = self.env._(
                    "Not sent to ARCA: %s, before it in the batch, was rejected.", rejected.display_name
                )
            failed.update(dict.fromkeys(rest, rest_msg))
        if rejected.exists():
            rejected.sudo().write(xml_values)
        return failed, pending

    def _ff_post_chunk(self, soft):
        """Post a chunk of invoices of the same (company, journal, document type) with one FECAESolicitar.

        Returns (validated, {invoice: error message}, pending) where pending are the invoices ARCA did not
        evaluate because a previous one of the chunk was rejected.
        """
        Move = self.browse()
        cr = self.env.cr
        self._ff_lock()
        first = self[0]
        client, auth, transport = first.company_id._l10n_ar_get_connection("wsfe")._get_client(return_transport=True)

        # Each invoice goes through the whole _post chain; l10n_ar_edi skips the CAE request for the ids of
        # the batch and does not commit. One savepoint before each posting: ARCA rejections are always an
        # approved prefix plus a rejected suffix, so rolling back to the first rejected savepoint undoes
        # exactly that suffix.
        batch_ctx = {"l10n_ar_batch_ids": tuple(self.ids), "l10n_ar_invoice_skip_commit": True}
        posted, savepoints, details, failed = Move, [], [], {}
        for inv in self:
            sp = cr.savepoint(flush=True)
            try:
                super(AccountMove, inv.with_context(**batch_ctx))._post(soft=soft)
                if hasattr(inv, "_check_vat_condition"):
                    inv._check_vat_condition()
                inv.l10n_ar_check_rate()
                details.append(inv.wsfe_get_cae_request(client)["FeDetReq"][0]["FECAEDetRequest"])
            except UserError as error:
                sp.close(rollback=True)
                failed[inv] = str(error)
                continue
            posted |= inv
            savepoints.append(sp)
        if not posted:
            return Move, failed, Move

        request = {
            "FeCabReq": {
                "CantReg": len(details),
                "PtoVta": first.journal_id.l10n_ar_afip_pos_number,
                "CbteTipo": first.l10n_latam_document_type_id.code,
            },
            "FeDetReq": {"FECAEDetRequest": details},
        }
        first._ws_verify_request_data(client, auth, "FECAESolicitar", request)

        start = time.monotonic()
        response = lost = None
        try:
            response = posted._ff_send(client, auth, request)
        except Exception as error:  # noqa: BLE001
            lost = error
            _logger.warning("ff: no answer for %s documents: %r", len(posted), error)
        elapsed = time.monotonic() - start

        values_list, first_bad, bad_msg, retry = [], None, "", True
        header_codes = [str(err.Code) for err in response.Errors.Err] if response and response.Errors else []
        if lost is not None or "10016" in header_codes:
            values_list, last = posted._ff_recover(details, client, auth)
            # A numbering mismatch rejects the rest too: do not retry them.
            retry = False
            if len(values_list) < len(posted):
                first_bad = len(values_list)
                bad_msg = posted[first_bad]._ff_unrecovered_msg(
                    lost, response, header_codes, details[first_bad]["CbteDesde"], last
                )
        else:
            results = {}
            if response.FeDetResp:
                results = {r.CbteDesde: r for r in response.FeDetResp.FECAEDetResponse}
            # A header error without details (auth, service) affects the whole chunk: do not retry.
            retry = bool(results)
            for idx, (inv, detail) in enumerate(zip(posted, details)):
                result = results.get(detail["CbteDesde"])
                obs_codes, obs = [], ""
                if result and result.Observaciones:
                    obs = "".join(f"\n* Code {ob.Code}: {ob.Msg}" for ob in result.Observaciones.Obs)
                    obs_codes = [str(ob.Code) for ob in result.Observaciones.Obs]
                if not result or result.Resultado != "A":
                    errors = (
                        "".join(f"\n* Code {e.Code}: {e.Msg}" for e in response.Errors.Err) if response.Errors else ""
                    )
                    first_bad = idx
                    bad_msg = inv._prepare_return_msg("wsfe", errors, obs, "", header_codes + obs_codes)
                    break
                values_list.append(
                    {
                        "l10n_ar_afip_auth_mode": "CAE",
                        "l10n_ar_afip_auth_code": str(result.CAE),
                        "l10n_ar_afip_auth_code_due": datetime.strptime(result.CAEFchVto, "%Y%m%d").date(),
                        "l10n_ar_afip_result": result.Resultado,
                        "_obs": obs and inv._prepare_return_msg("wsfe", "", obs, "", obs_codes),
                    }
                )

        xml_request, xml_response = transport.xml_request, transport.xml_response
        approved, pending = posted[: len(values_list)], Move
        if first_bad is not None:
            savepoints[first_bad].rollback()
            rejected_failed, pending = posted._ff_reject_from(
                first_bad,
                bad_msg,
                lost is None and retry,
                lost is None and "10016" in header_codes,
                {"l10n_ar_afip_xml_request": xml_request, "l10n_ar_afip_xml_response": xml_response},
            )
            failed.update(rejected_failed)
        # Releasing the outermost savepoint releases the nested ones (or the ones the rollback destroyed).
        cr.execute(SQL("RELEASE SAVEPOINT %s", SQL.identifier(savepoints[0].name)))
        for sp in savepoints:
            sp.closed = True

        for inv, values in zip(approved, values_list):
            obs = values.pop("_obs", "")
            inv.sudo().write(dict(values, l10n_ar_afip_xml_request=xml_request, l10n_ar_afip_xml_response=xml_response))
            if obs:
                inv.message_post(
                    body=Markup("<p><b>%s%s</b></p>") % (self.env._("ARCA Messages"), plaintext2html(obs, "em"))
                )
        _logger.info(
            "ff: journal %s type %s: %s sent, %s approved, %s rejected, %s pending, FECAESolicitar %.3fs",
            first.journal_id.id,
            first.l10n_latam_document_type_id.code,
            len(posted),
            len(approved),
            len(failed),
            len(pending),
            elapsed,
        )
        if not self.env.context.get("l10n_ar_invoice_skip_commit"):
            cr.commit()  # pragma pylint: disable=invalid-commit
        return approved, failed, pending

    # -------------------------------------------------------------------------
    # Background post
    # -------------------------------------------------------------------------

    @api.model
    def _cron_background_post_invoices(self, ids=None):
        """Post the due invoices of batch journals in chunks of `account_background_post.batch_size`, one
        action_post per chunk. The other invoices keep being posted one by one."""
        moves = self.browse(ids) if ids is not None else self._get_background_post_due_moves()
        if not moves.filtered("journal_id.l10n_ar_batch_cae"):
            return super()._cron_background_post_invoices(ids=ids)
        # ARCA rejects a date older than the last authorized one: oldest first, immediate before scheduled.
        moves = moves.sorted(lambda m: (bool(m.background_post_date), m.invoice_date or m.date, m.id))
        size = max(1, self._get_background_post_batch_size())
        batch = moves.filtered("journal_id.l10n_ar_batch_cae")
        chunks = [batch[i : i + size] for i in range(0, len(batch), size)] + [move for move in moves - batch]
        cron = self.env["ir.cron"]
        remaining_time = cron._commit_progress(remaining=len(moves))
        for index, chunk in enumerate(chunks):
            if remaining_time <= 0:
                _logger.info(
                    "Background post cron ran out of time, %s chunks left for the next run", len(chunks) - index
                )
                break
            self.env.cr.cache[ERRORS_KEY] = {}
            try:
                chunk.with_context(l10n_ar_batch_collect_errors=True).action_post()
            except Exception as exp:  # noqa: BLE001
                # Not an ARCA rejection of a batch (those are collected): retry what is left one by one.
                self.env.cr.rollback()
                if len(chunk) == 1:
                    self.env.cr.cache.setdefault(ERRORS_KEY, {})[chunk.id] = exp
                    chunk = self.browse()
                else:
                    _logger.warning("Background post chunk failed, retrying one by one: %s", exp)
                for move in chunk.filtered(lambda m: m.state == "draft"):
                    try:
                        move.action_post()
                    except Exception as move_exp:  # noqa: BLE001
                        self.env.cr.rollback()
                        self.env.cr.cache.setdefault(ERRORS_KEY, {})[move.id] = move_exp
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
