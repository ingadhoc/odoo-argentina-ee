"""Monkey patch of l10n_ar_edi to request wsfe CAE in batches.

Only wsfe customer invoices go through the batch flow; everything else (wsfex,
wsbfe, vendor bills, dummy validation) keeps the original code path.
"""

import logging
import time
from datetime import datetime

from markupsafe import Markup
from odoo import _
from odoo.addons.l10n_ar_edi.models.account_move import AccountMove as ArMove
from odoo.exceptions import UserError
from odoo.tools import SQL, plaintext2html
from psycopg2 import errors as pg_errors

_logger = logging.getLogger(__name__)

MODULE = "l10n_ar_edi_ff"
ERRORS_KEY = f"{MODULE}.errors"
_original_post = ArMove._post


def _param(env, key, default):
    return env["ir.config_parameter"].sudo().get_param(f"{MODULE}.{key}", default)


def _enabled(env):
    return MODULE in env.registry._init_modules and _param(env, "enabled", "1") == "1"


def _batchable(move):
    return (
        move.is_invoice()
        and move.country_code == "AR"
        and move.move_type in ("out_invoice", "out_refund")
        and move.journal_id.l10n_ar_afip_ws == "wsfe"
        and not move.l10n_ar_afip_auth_code
        and not move._is_dummy_afip_validation()
    )


def _post(self, soft=True):
    if not _enabled(self.env):
        return _original_post(self, soft=soft)
    batchable = self.filtered(_batchable)
    if not batchable:
        return _original_post(self, soft=soft)

    rest = self - batchable
    validated = _original_post(rest, soft=soft) if rest else self.browse()
    size = max(1, int(_param(self.env, "batch_size", "20")))
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

    if failed and self.env.context.get("ff_collect_errors"):
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
                _(
                    "These documents were validated in ARCA:\n   * %(ok)s\n\nThese documents were not:\n%(ko)s",
                    ok="\n   * ".join(validated.mapped("name")),
                    ko=lines,
                )
            )
        raise UserError(_("We couldn't validate the documents in ARCA:\n%s", lines))
    return validated


def _ff_lock(self):
    """Serialize CAE requests per (company, journal, document type).

    The transaction lock is released by the commit at the end of each chunk.
    """
    inv = self[0]
    key = f"{MODULE}:{inv.company_id.id}:{inv.journal_id.id}:{inv.l10n_latam_document_type_id.id}"
    cr = self.env.cr
    cr.execute("SET LOCAL lock_timeout = %s", [_param(self.env, "lock_timeout", "10s")])
    try:
        with cr.savepoint(flush=False):
            cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [key])
    except pg_errors.LockNotAvailable:
        raise UserError(
            _(
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

    Returns a list with, for each document in order, the values to write or False. Stops at the first
    one that is not registered (or does not match), because ARCA authorizes in order.
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
    return recovered


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

    # One savepoint before each posting: ARCA rejections are always an approved prefix plus a
    # rejected suffix, so rolling back to the first rejected savepoint undoes exactly that suffix.
    posted, savepoints, details, failed = Move, [], [], {}
    for inv in self:
        sp = cr.savepoint(flush=True)
        try:
            super(ArMove, inv)._post(soft=soft)
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
        values_list = posted._ff_recover(details, client, auth)
        if len(values_list) < len(posted):
            first_bad = len(values_list)
            bad_msg = repr(lost) if lost is not None else _("Error 10016 and ARCA does not have this document")
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

    xml_request, xml_response = transport.xml_request, transport.xml_response
    approved, pending = posted[: len(values_list)], Move
    if first_bad is not None:
        savepoints[first_bad].rollback()
        rejected = posted[first_bad]
        failed[rejected] = bad_msg or _("Rejected by ARCA")
        # Only the first rejected was evaluated; ARCA skips the rest, so they are retried.
        pending = posted[first_bad + 1 :] if lost is None and retry else Move
        if not pending:
            for inv in posted[first_bad + 1 :]:
                failed[inv] = bad_msg
        if rejected.exists():
            rejected.sudo().write({"l10n_ar_afip_xml_request": xml_request, "l10n_ar_afip_xml_response": xml_response})
    # Releasing the outermost savepoint releases the nested ones (or the ones the rollback destroyed).
    cr.execute(SQL("RELEASE SAVEPOINT %s", SQL.identifier(savepoints[0].name)))
    for sp in savepoints:
        sp.closed = True

    for inv, values in zip(approved, values_list):
        obs = values.pop("_obs", "")
        inv.sudo().write(dict(values, l10n_ar_afip_xml_request=xml_request, l10n_ar_afip_xml_response=xml_response))
        if obs:
            inv.message_post(body=Markup("<p><b>%s%s</b></p>") % (_("ARCA Messages"), plaintext2html(obs, "em")))
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


def apply():
    ArMove._post = _post
    ArMove._ff_lock = _ff_lock
    ArMove._ff_send = _ff_send
    ArMove._ff_recover = _ff_recover
    ArMove._ff_post_chunk = _ff_post_chunk
    _logger.info("%s: l10n_ar_edi AccountMove._post patched", MODULE)
