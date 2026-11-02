from datetime import datetime

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from ..models.account_move import PARAM


class L10nArEdiFfRecover(models.TransientModel):
    _name = "l10n_ar_edi_ff.recover"
    _description = "Recover documents authorized by ARCA"

    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[('l10n_ar_afip_pos_system', '=', 'RAW_MAW')]",
    )
    company_id = fields.Many2one(related="journal_id.company_id")
    currency_id = fields.Many2one(related="company_id.currency_id")
    document_type_id = fields.Many2one(
        "l10n_latam.document.type",
        required=True,
        domain="[('id', 'in', available_document_type_ids)]",
    )
    available_document_type_ids = fields.Many2many(
        "l10n_latam.document.type", compute="_compute_available_document_type_ids"
    )
    number_from = fields.Integer(
        readonly=True,
        help="Next number of Odoo. Documents are numbered in order, so the recovery starts here.",
    )
    number_to = fields.Integer(help="By default, the last number authorized in ARCA.")
    line_ids = fields.One2many("l10n_ar_edi_ff.recover.line", "wizard_id")
    state = fields.Selection([("setup", "Setup"), ("review", "Review")], default="setup", required=True)

    @api.depends("journal_id")
    def _compute_available_document_type_ids(self):
        for wizard in self:
            journal = wizard.journal_id
            wizard.available_document_type_ids = (
                self.env["l10n_latam.document.type"].search(journal._get_journal_codes_domain()) if journal else False
            )

    @api.onchange("journal_id", "document_type_id")
    def _onchange_range(self):
        for wizard in self.filtered(lambda w: w.journal_id and w.document_type_id):
            last_here = wizard._last_number_here()
            last_there = wizard.journal_id._l10n_ar_get_afip_last_invoice_number(wizard.document_type_id)
            wizard.number_from = last_here + 1
            wizard.number_to = max(last_there, last_here)

    def _last_number_here(self):
        self.ensure_one()
        last = self.env["account.move"].search(
            [
                ("journal_id", "=", self.journal_id.id),
                ("l10n_latam_document_type_id", "=", self.document_type_id.id),
                ("state", "=", "posted"),
            ],
            order="sequence_number desc",
            limit=1,
        )
        return last._move_batch_number() if last else 0

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Recover documents from ARCA"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # ------------------------------------------------------------------ fetch

    def action_fetch(self):
        """Ask ARCA for every number of the range and propose the draft each one goes to."""
        self.ensure_one()
        self.number_from = self._last_number_here() + 1
        if self.number_to < self.number_from:
            raise UserError(self.env._("Odoo already has every document up to number %s.", self.number_to))
        limit = int(self.env["ir.config_parameter"].sudo().get_param(f"{PARAM}.recover_wizard_limit", 100))
        if self.number_to - self.number_from + 1 > limit:
            raise UserError(
                self.env._(
                    "Each number is a query to ARCA: recover %(limit)s or less at a time, or raise the system "
                    "parameter %(param)s.",
                    limit=limit,
                    param=f"{PARAM}.recover_wizard_limit",
                )
            )
        client, auth, _transport = self.company_id._l10n_ar_get_connection("wsfe")._get_client(return_transport=True)
        self.line_ids.unlink()
        taken = self.env["account.move"]
        lines = []
        for number in range(self.number_from, self.number_to + 1):
            res = client.service.FECompConsultar(
                auth,
                {
                    "CbteTipo": self.document_type_id.code,
                    "CbteNro": number,
                    "PtoVta": self.journal_id.l10n_ar_afip_pos_number,
                },
            )
            if res.Errors or not res.ResultGet:
                lines.append({"number": number, "note": self.env._("ARCA has no document with this number.")})
                continue
            values = self._prepare_line(number, res.ResultGet, taken)
            taken |= self.env["account.move"].browse(values.get("move_id") or [])
            lines.append(values)
        self.write({"state": "review", "line_ids": [Command.create(values) for values in lines]})
        return self._reopen()

    def _prepare_line(self, number, got, taken):
        self.ensure_one()
        values = {
            "number": number,
            "date": datetime.strptime(str(got.CbteFch), "%Y%m%d").date(),
            "amount_total": float(got.ImpTotal or 0),
            "document_number": str(got.DocNro or ""),
            "auth_mode": got.EmisionTipo,
            "auth_code": str(got.CodAutorizacion),
            "auth_code_due": datetime.strptime(str(got.FchVto), "%Y%m%d").date(),
            "result": got.Resultado,
            "action": "skip",
        }
        partner = self._find_partner(got)
        values["partner_id"] = partner.id
        draft = self._find_draft(got, partner, taken)
        if draft:
            values.update(move_id=draft.id, action="match")
        else:
            values["note"] = self.env._(
                "No draft of Odoo with this customer, date and total. Pick one in the Draft column, or load it "
                "as a draft and run the wizard again."
            )
        return values

    def _find_partner(self, got):
        """The customer ARCA reports, by its identification. Without a number it is the anonymous final consumer."""
        self.ensure_one()
        number = str(got.DocNro or "").strip()
        if not number or number == "0":
            return self.env.ref("l10n_ar.par_cfa", raise_if_not_found=False) or self.env["res.partner"]
        candidates = [number]
        if len(number) == 11:
            candidates.append("%s-%s-%s" % (number[:2], number[2:10], number[10:]))
        return self.env["res.partner"].search(
            [
                ("vat", "in", candidates),
                ("l10n_latam_identification_type_id.l10n_ar_afip_code", "=", str(got.DocTipo)),
                ("company_id", "in", (False, self.company_id.id)),
            ],
            limit=1,
        )

    def _find_draft(self, got, partner, taken):
        """The draft of the journal with the same customer, total and date, not proposed for another number.

        A draft without date also fits: Odoo would date it when posting. One with another date is not proposed,
        since an old draft with the same customer and total is a common thing; the user can still pick it.
        """
        self.ensure_one()
        if not partner:
            return self.env["account.move"]
        date = datetime.strptime(str(got.CbteFch), "%Y%m%d").date()
        drafts = self.env["account.move"].search(
            [
                ("journal_id", "=", self.journal_id.id),
                ("l10n_latam_document_type_id", "=", self.document_type_id.id),
                ("state", "=", "draft"),
                ("l10n_ar_afip_auth_code", "=", False),
                ("commercial_partner_id", "=", partner.commercial_partner_id.id),
                ("invoice_date", "in", (date, False)),
                ("id", "not in", taken.ids),
            ],
            order="invoice_date, id",
        )
        total = float(got.ImpTotal or 0)
        drafts = drafts.filtered(lambda m: not m.currency_id.compare_amounts(m.amount_total, total))
        return (drafts.filtered("invoice_date") or drafts)[:1]

    # ------------------------------------------------------------------ apply

    def action_apply(self):
        """Assign what is marked, from the lowest number up.

        Odoo numbers with its own sequence, so the numbers are taken in order: a skipped number stops the ones
        after it."""
        self.ensure_one()
        lines = self.line_ids.sorted("number")
        todo = self.env["l10n_ar_edi_ff.recover.line"]
        for line in lines:
            if line.action == "skip":
                break
            todo |= line
        if skipped := (lines - todo).filtered(lambda line: line.action != "skip"):
            raise UserError(
                self.env._(
                    "Numbers are taken in order: number %(skipped)s is skipped, so %(next)s cannot be recovered.",
                    skipped=(lines - todo)[0].number,
                    next=skipped[0].number,
                )
            )
        if not todo:
            raise UserError(self.env._("No document is marked to assign."))
        client, auth, _transport = self.company_id._l10n_ar_get_connection("wsfe")._get_client(return_transport=True)
        done = self.env["account.move"]
        for line in todo:
            done |= line._apply(client, auth)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Recovered documents"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", done.ids)],
        }


class L10nArEdiFfRecoverLine(models.TransientModel):
    _name = "l10n_ar_edi_ff.recover.line"
    _description = "Document of ARCA to recover"
    _order = "number"

    wizard_id = fields.Many2one("l10n_ar_edi_ff.recover", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="wizard_id.company_id")
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    number = fields.Integer(readonly=True)
    date = fields.Date(readonly=True)
    amount_total = fields.Monetary("Total", readonly=True)
    document_number = fields.Char("Identification", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer", readonly=True)
    move_id = fields.Many2one(
        "account.move",
        string="Draft",
        domain="[('journal_id', '=', parent.journal_id), ('state', '=', 'draft')]",
    )
    action = fields.Selection([("match", "Assign"), ("skip", "Skip")], required=True, default="skip")
    auth_mode = fields.Char(readonly=True)
    auth_code = fields.Char("CAE", readonly=True)
    auth_code_due = fields.Date("CAE due date", readonly=True)
    result = fields.Char(readonly=True)
    note = fields.Char(readonly=True)

    def _apply(self, client, auth):
        """Give the draft the number and authorization ARCA already has for it, if it is that document."""
        self.ensure_one()
        move = self.move_id
        if not move or move.state != "draft":
            raise UserError(self.env._("Number %s: choose a draft to assign it to.", self.number))
        values = {
            "l10n_ar_afip_auth_mode": self.auth_mode,
            "l10n_ar_afip_auth_code": self.auth_code,
            "l10n_ar_afip_auth_code_due": self.auth_code_due,
            "l10n_ar_afip_result": self.result,
        }
        # Writing the date recomputes taxes (perceptions by date, for one): only when it changes
        if move.invoice_date != self.date:
            values["invoice_date"] = self.date
        move.sudo().write(values)
        # With the authorization written, posting does not ask ARCA again; no commit until the number is checked
        move.with_context(l10n_ar_invoice_skip_commit=True).action_post()
        if move.state != "posted" or move._move_batch_number() != self.number:
            raise UserError(
                self.env._(
                    "Number %(number)s was given number %(got)s by Odoo: nothing was recovered.",
                    number=self.number,
                    got=move.name,
                )
            )
        self._check_same_document(move, client, auth)
        move.message_post(
            body=self.env._(
                "Recovered from ARCA with the recovery wizard: number %(number)s, CAE %(cae)s.",
                number=self.number,
                cae=self.auth_code,
            )
        )
        return move

    def _check_same_document(self, move, client, auth):
        """The posted draft has to be what ARCA authorized, field by field, as in the automatic recovery."""
        self.ensure_one()
        wizard = self.wizard_id
        res = client.service.FECompConsultar(
            auth,
            {
                "CbteTipo": wizard.document_type_id.code,
                "CbteNro": self.number,
                "PtoVta": wizard.journal_id.l10n_ar_afip_pos_number,
            },
        )
        detail = move.wsfe_get_cae_request(client)["FeDetReq"][0]["FECAEDetRequest"]
        if res.Errors or not res.ResultGet or not move._move_batch_same_document(detail, res.ResultGet):
            raise UserError(
                self.env._(
                    "Number %(number)s: %(draft)s, once posted, is not the document ARCA authorized (it differs in "
                    "customer, date or amounts; it now totals %(total)s and ARCA authorized %(arca)s). Nothing was "
                    "recovered.",
                    number=self.number,
                    draft=move.display_name,
                    total=move.amount_total,
                    arca=self.amount_total,
                )
            )
