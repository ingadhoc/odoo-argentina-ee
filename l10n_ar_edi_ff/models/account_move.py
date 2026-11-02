import logging
import os
import time
from datetime import datetime

from markupsafe import Markup
from odoo import api, models
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools import SQL, plaintext2html
from psycopg2 import errors as pg_errors

_logger = logging.getLogger(__name__)

PARAM = "l10n_ar_edi_ff"
ERRORS_KEY = f"{PARAM}.errors"
# (journal, document type) whose gap with ARCA was left for the recovery wizard
GAPS_KEY = f"{PARAM}.gaps"
FLAG_ENV = "ODOO_FLAG_L10N_AR_BATCH_CAE"
FLAG_PARAM = f"{PARAM}.batch_cae"
# What FECompConsultar returns of a document, compared with the request that would send it. The number is left
# out: it is what the recovery assigns.
MATCH_FIELDS = (
    "CbteFch",
    "Concepto",
    "DocTipo",
    "DocNro",
    "MonId",
    "ImpTotal",
    "ImpTotConc",
    "ImpNeto",
    "ImpOpEx",
    "ImpTrib",
    "ImpIVA",
    "FchServDesde",
    "FchServHasta",
)


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # Posting
    # -------------------------------------------------------------------------

    @api.model
    def _move_batch_enabled(self):
        """Batch CAE requests are on for every wsfe journal or for none. The environment variable, when set,
        wins over the system parameter."""
        value = os.environ.get(FLAG_ENV)
        if value is None:
            value = self.env["ir.config_parameter"].sudo().get_param(FLAG_PARAM, "")
        return value.strip().lower() in ("1", "true", "yes")

    def _move_batch_eligible(self):
        self.ensure_one()
        return (
            self.journal_id.l10n_ar_afip_ws == "wsfe"
            and self.is_invoice()
            and self.country_code == "AR"
            and self.move_type in ("out_invoice", "out_refund")
            and not self.l10n_ar_afip_auth_code
            and not self._is_dummy_afip_validation()
        )

    def _post(self, soft=True):
        # Inside a batch every invoice goes through the regular chain one by one: do not batch again.
        # force_background_post defers the invoices: the background post cron batches them later.
        if (
            self.env.context.get("l10n_ar_batch_ids")
            or self.env.context.get("force_background_post")
            or not self._move_batch_enabled()
        ):
            return super()._post(soft=soft)
        batchable = self.filtered(lambda m: m._move_batch_eligible())
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
                done, chunk_failed, pending = chunk._move_batch_post_chunk(soft)
                validated |= done
                failed.update(chunk_failed)
                queue = pending.ids + queue[size:]

        gaps = self.env.cr.cache.pop(GAPS_KEY, set())
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
                msg = self.env._(
                    "These documents were validated in ARCA:\n   * %(ok)s\n\nThese documents were not:\n%(ko)s",
                    ok="\n   * ".join(validated.mapped("name")),
                    ko=lines,
                )
            else:
                msg = self.env._("We couldn't validate the documents in ARCA:\n%s", lines)
            if gaps:
                journal_id, document_type_id = next(iter(gaps))
                action = self.env["ir.actions.act_window"]._for_xml_id("l10n_ar_edi_ff.action_recover_invoices")
                action["context"] = {
                    "default_journal_id": journal_id,
                    "default_document_type_id": document_type_id,
                }
                raise RedirectWarning(msg, action, self.env._("Recover documents from ARCA"))
            raise UserError(msg)
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

    def _move_batch_lock(self):
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

    def _move_batch_send(self, client, auth, request):
        """Isolated so tests can simulate a lost response."""
        return client.service.FECAESolicitar(auth, request)

    def _move_batch_number(self):
        self.ensure_one()
        return self._l10n_ar_get_document_number_parts(
            self.l10n_latam_document_number, self.l10n_latam_document_type_id.code
        )["invoice_number"]

    @api.model
    def _move_batch_same_document(self, detail, got):
        """Whether what ARCA registered (`got`) is the document of this request detail, field by field."""

        def norm(value):
            # ARCA answers 0 / empty where Odoo sends 0.00 / None
            return None if value is None else (self._l10n_ar_parse_xml_value(str(value)) or None)

        return all(norm(detail.get(field)) == norm(getattr(got, field, None)) for field in MATCH_FIELDS)

    def _move_batch_recover_gap(self, first_number, soft, client, auth, lost, response, header_codes, xml_values):
        """Bring what ARCA registered from `first_number` on, which Odoo does not have. This chunk is in draft.

        Each number goes, in order, to the draft that is the same document: first the invoices of this chunk,
        then the other drafts of the journal, oldest first. ARCA returns no lines, so equal drafts are the same
        document for it and the first one takes the number.

        Returns (recovered, {invoice: error message}, pending). The rest of the chunk is sent again only when
        the whole gap was recovered: until then ARCA keeps answering 10016.
        """
        Move = self.browse()
        journal, doc_type = self[0].journal_id, self[0].l10n_latam_document_type_id
        try:
            last = journal._l10n_ar_get_afip_last_invoice_number(doc_type)
        except Exception as error:  # noqa: BLE001
            # ARCA is most likely still down. Nothing is confirmed: the whole chunk stays in draft and the next
            # attempt reconciles it through the 10016 path.
            _logger.warning("batch CAE: could not check %s documents in ARCA: %r", len(self), error)
            msg = self.env._(
                "ARCA did not answer and we could not check what it registered: %(error)s\n\n"
                "The document stays in draft. If ARCA did register it, validating it again recovers its "
                "authorization instead of reporting it twice.",
                error=repr(lost if lost is not None else error),
            )
            # The request is the only trace of what may be registered in ARCA
            self.sudo().write(xml_values)
            return Move, dict.fromkeys(self, msg), Move

        gap = range(first_number, last + 1)
        limit = max(1, int(self.env["ir.config_parameter"].sudo().get_param(f"{PARAM}.recover_limit", 20)))
        if len(gap) > limit:
            msg = self.env._(
                "ARCA has %(count)s documents (numbers %(first)s to %(last)s) that Odoo does not have, more than "
                "the %(limit)s that are recovered automatically. Recover them before validating again.",
                count=len(gap),
                first=first_number,
                last=last,
                limit=limit,
            )
            self.sudo().write(xml_values)
            self._move_batch_leave_gap()
            return Move, dict.fromkeys(self, msg), Move

        recovered = Move
        for number in gap:
            match = self._move_batch_recover_number(number, recovered, soft, client, auth)
            if not match:
                break
            recovered |= match
        _logger.info(
            "batch CAE: recovered %s of %s documents from ARCA (%s to %s)", len(recovered), len(gap), first_number, last
        )
        rest = self - recovered
        if not recovered:
            # Nothing to bring: ARCA registered nothing of this chunk, or what it has is no draft of Odoo
            msg = self[0]._move_batch_unrecovered_msg(lost, response, header_codes, first_number, last)
            if gap:
                msg = self.env._(
                    "ARCA registered number %(number)s and no draft of Odoo is that document.", number=first_number
                ) + ("\n\n" + msg)
                self._move_batch_leave_gap()
            failed, _pending = self._move_batch_reject_from(0, msg, False, lost is None, xml_values)
            return Move, failed, Move
        self._move_batch_flag_twins(recovered)
        if len(recovered) == len(gap):
            return recovered, {}, rest
        msg = self.env._(
            "ARCA registered number %(number)s and no draft of Odoo is that document. Number sent by Odoo: "
            "%(odoo)s. Last number authorized in ARCA: %(arca)s.",
            number=gap[len(recovered)],
            odoo=first_number,
            arca=last,
        )
        rest.sudo().write(xml_values)
        self._move_batch_leave_gap()
        return recovered, dict.fromkeys(rest, msg), Move

    def _move_batch_leave_gap(self):
        self.env.cr.cache.setdefault(GAPS_KEY, set()).add(
            (self[0].journal_id.id, self[0].l10n_latam_document_type_id.id)
        )

    def _move_batch_recover_number(self, number, taken, soft, client, auth):
        """The draft that takes `number` from ARCA, posted with its authorization, or an empty recordset."""
        Move = self.browse()
        journal, doc_type = self[0].journal_id, self[0].l10n_latam_document_type_id
        try:
            res = client.service.FECompConsultar(
                auth, {"CbteTipo": doc_type.code, "CbteNro": number, "PtoVta": journal.l10n_ar_afip_pos_number}
            )
        except Exception as error:  # noqa: BLE001
            _logger.warning("batch CAE: could not read number %s from ARCA: %r", number, error)
            return Move
        got = res.ResultGet
        if res.Errors or not got or got.Resultado not in ("A", "O"):
            return Move
        others = self.search(
            [
                ("company_id", "=", self[0].company_id.id),
                ("journal_id", "=", journal.id),
                ("l10n_latam_document_type_id", "=", doc_type.id),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "draft"),
                ("l10n_ar_afip_auth_code", "=", False),
                ("id", "not in", (self | taken).ids),
            ],
            order="invoice_date, id",
        )
        total = float(got.ImpTotal)
        for inv in (self - taken) | others:
            if inv.currency_id.compare_amounts(inv.amount_total, total):
                continue
            if inv._move_batch_take(number, got, soft, client):
                return inv
        return Move

    def _move_batch_take(self, number, got, soft, client):
        """Post this draft with `number` and the authorization ARCA gave it, if it is that document."""
        self.ensure_one()
        sp = self.env.cr.savepoint(flush=True)
        try:
            ctx = {"l10n_ar_batch_ids": (self.id,), "l10n_ar_invoice_skip_commit": True}
            super(AccountMove, self.with_context(**ctx))._post(soft=soft)
            same = (
                self.state == "posted"
                and self._move_batch_number() == number
                and self._move_batch_same_document(
                    self.wsfe_get_cae_request(client)["FeDetReq"][0]["FECAEDetRequest"], got
                )
            )
        except UserError:
            same = False
        if not same:
            self._move_batch_rollback(sp)
        sp.close(rollback=False)
        if not same:
            return False
        self.sudo().write(
            {
                "l10n_ar_afip_auth_mode": got.EmisionTipo,
                "l10n_ar_afip_auth_code": str(got.CodAutorizacion),
                "l10n_ar_afip_auth_code_due": datetime.strptime(got.FchVto, "%Y%m%d").date(),
                "l10n_ar_afip_result": got.Resultado,
            }
        )
        self.message_post(
            body=self.env._(
                "ARCA had authorized this document with number %(number)s and CAE %(cae)s, but its answer did not "
                "reach Odoo. The authorization was recovered from ARCA.",
                number=number,
                cae=got.CodAutorizacion,
            )
        )
        return True

    def _move_batch_flag_twins(self, recovered):
        """Warn on the drafts equal to a recovered document: it may be a copy made after the answer got lost.

        The invoices of this chunk are being validated on purpose, so they are not warned."""
        for inv in recovered:
            twins = self.search(
                [
                    ("journal_id", "=", inv.journal_id.id),
                    ("l10n_latam_document_type_id", "=", inv.l10n_latam_document_type_id.id),
                    ("commercial_partner_id", "=", inv.commercial_partner_id.id),
                    ("state", "=", "draft"),
                    ("l10n_ar_afip_auth_code", "=", False),
                    ("invoice_date", "in", (inv.invoice_date, False)),
                    ("id", "not in", self.ids),
                ]
            ).filtered(lambda m, inv=inv: not m.currency_id.compare_amounts(m.amount_total, inv.amount_total))
            for twin in twins:
                twin.message_post(
                    body=self.env._(
                        "%(doc)s, identical to this one, was recovered from ARCA. Check that this one is not a "
                        "duplicate before validating it.",
                        doc=inv.display_name,
                    )
                )

    def _move_batch_unrecovered_msg(self, lost, response, codes, number, last):
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

    def _move_batch_reject_from(self, index, msg, retry, numbering, xml_values):
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

    def _move_batch_evaluate(self, details, response, header_codes):
        """Read what ARCA answered to this posted chunk.

        Returns (values for the approved prefix, index of the first document not approved or None, its error
        message, whether the documents after it can be retried)."""
        values_list, first_bad, bad_msg, retry = [], None, "", True
        results = {}
        if response.FeDetResp:
            results = {r.CbteDesde: r for r in response.FeDetResp.FECAEDetResponse}
        # A header error without details (auth, service) affects the whole chunk: do not retry.
        retry = bool(results)
        for idx, (inv, detail) in enumerate(zip(self, details)):
            result = results.get(detail["CbteDesde"])
            obs_codes, obs = [], ""
            if result and result.Observaciones:
                obs = "".join(f"\n* Code {ob.Code}: {ob.Msg}" for ob in result.Observaciones.Obs)
                obs_codes = [str(ob.Code) for ob in result.Observaciones.Obs]
            if not result or result.Resultado != "A":
                errors = "".join(f"\n* Code {e.Code}: {e.Msg}" for e in response.Errors.Err) if response.Errors else ""
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
        return values_list, first_bad, bad_msg, retry

    def _move_batch_rollback(self, savepoint):
        """Roll back to `savepoint` and forget the numbers handed out after it.

        The sequence cache of Odoo lives in the cursor and a savepoint rollback does not clear it: the next
        posting would take the number after the undone ones, which is the one ARCA expects, and the gap would
        never be noticed."""
        savepoint.rollback()
        self.env.cr.cache.pop("sequence.mixin", None)

    def _move_batch_release(self, savepoints):
        """Releasing the outermost savepoint releases the nested ones (or the ones a rollback destroyed)."""
        self.env.cr.execute(SQL("RELEASE SAVEPOINT %s", SQL.identifier(savepoints[0].name)))
        for sp in savepoints:
            sp.closed = True

    def _move_batch_post_chunk(self, soft):
        """Post a chunk of invoices of the same (company, journal, document type) with one FECAESolicitar.

        Returns (validated, {invoice: error message}, pending) where pending are the invoices ARCA did not
        evaluate because a previous one of the chunk was rejected.
        """
        Move = self.browse()
        cr = self.env.cr
        self._move_batch_lock()
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
                if inv.state != "posted":
                    # Some module in the chain deferred it instead of posting: keep its changes, no CAE.
                    sp.close(rollback=False)
                    continue
                if hasattr(inv, "_check_vat_condition"):
                    inv._check_vat_condition()
                inv.l10n_ar_check_rate()
                details.append(inv.wsfe_get_cae_request(client)["FeDetReq"][0]["FECAEDetRequest"])
            except UserError as error:
                self._move_batch_rollback(sp)
                sp.close(rollback=False)
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
            response = posted._move_batch_send(client, auth, request)
        except Exception as error:  # noqa: BLE001
            lost = error
            _logger.warning("batch CAE: no answer for %s documents: %r", len(posted), error)
        elapsed = time.monotonic() - start

        xml_values = {
            "l10n_ar_afip_xml_request": transport.xml_request,
            "l10n_ar_afip_xml_response": transport.xml_response,
        }
        header_codes = [str(err.Code) for err in response.Errors.Err] if response and response.Errors else []
        if lost is not None or "10016" in header_codes:
            # ARCA may have registered documents Odoo does not know: the chunk goes back to draft and each number
            # ARCA has goes to the draft that is that document.
            self._move_batch_rollback(savepoints[0])
            self._move_batch_release(savepoints)
            approved, gap_failed, pending = posted._move_batch_recover_gap(
                details[0]["CbteDesde"], soft, client, auth, lost, response, header_codes, xml_values
            )
            failed.update(gap_failed)
        else:
            values_list, first_bad, bad_msg, retry = posted._move_batch_evaluate(details, response, header_codes)
            approved, pending = posted[: len(values_list)], Move
            if first_bad is not None:
                self._move_batch_rollback(savepoints[first_bad])
                rejected_failed, pending = posted._move_batch_reject_from(first_bad, bad_msg, retry, False, xml_values)
                failed.update(rejected_failed)
            self._move_batch_release(savepoints)
            for inv, values in zip(approved, values_list):
                obs = values.pop("_obs", "")
                inv.sudo().write(dict(values, **xml_values))
                if obs:
                    inv.message_post(
                        body=Markup("<p><b>%s%s</b></p>") % (self.env._("ARCA Messages"), plaintext2html(obs, "em"))
                    )
        _logger.info(
            "batch CAE: journal %s type %s: %s sent, %s approved, %s rejected, %s pending, FECAESolicitar %.3fs",
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
        """Post the due invoices that can be batched in chunks of `account_background_post.batch_size`, one
        action_post per chunk, and leave the rest to the original cron, one by one."""
        if not self._move_batch_enabled():
            return super()._cron_background_post_invoices(ids=ids)
        moves = self.browse(ids) if ids is not None else self._get_background_post_due_moves()
        batch = moves.filtered(lambda m: m._move_batch_eligible())
        if not batch:
            return super()._cron_background_post_invoices(ids=ids)
        # ARCA rejects a date older than the last authorized one: oldest first, immediate before scheduled.
        batch = batch.sorted(lambda m: (bool(m.background_post_date), m.invoice_date or m.date, m.id))
        size = max(1, self._get_background_post_batch_size())
        cron = self.env["ir.cron"]
        remaining_time = cron._commit_progress(remaining=len(moves))
        for start in range(0, len(batch), size):
            if remaining_time <= 0:
                _logger.info(
                    "Background post cron ran out of time, %s invoices left for the next run", len(moves) - start
                )
                return
            chunk = batch[start : start + size]
            chunk._move_batch_background_post_chunk()
            # Every invoice of the chunk is done for this run: posted, rescheduled or given up.
            remaining_time = cron._commit_progress(processed=len(chunk))
        rest = moves - batch
        if rest and remaining_time > 0:
            # The original cron sets the remaining count to these invoices.
            super()._cron_background_post_invoices(ids=rest.ids)

    def _move_batch_background_post_chunk(self):
        """Post this chunk with one action_post; reschedule or give up on the invoices that fail."""
        self.env.cr.cache[ERRORS_KEY] = {}
        try:
            self.with_context(l10n_ar_batch_collect_errors=True).action_post()
        except Exception as exp:  # noqa: BLE001
            # Not an ARCA rejection of a batch (those are collected): retry what is left one by one.
            self.env.cr.rollback()
            if len(self) == 1:
                self.env.cr.cache.setdefault(ERRORS_KEY, {})[self.id] = exp
            else:
                _logger.warning("Background post chunk failed, retrying one by one: %s", exp)
                for move in self.filtered(lambda m: m.state == "draft"):
                    try:
                        move.action_post()
                    except Exception as move_exp:  # noqa: BLE001
                        self.env.cr.rollback()
                        self.env.cr.cache.setdefault(ERRORS_KEY, {})[move.id] = move_exp
        errors = self.env.cr.cache.pop(ERRORS_KEY, {})
        for move in self.browse(list(errors)):
            error = errors[move.id]
            move._move_batch_background_post_failed(error if isinstance(error, Exception) else UserError(error))

    def _move_batch_background_post_failed(self, error):
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
