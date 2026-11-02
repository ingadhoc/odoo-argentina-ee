from datetime import datetime

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from ..models.account_move import MATCH_FIELDS, PARAM

# VAT codes of ARCA for what is not taxed and what is exempt, reported apart from the aliquots
NOT_TAXED_CODE = "1"
EXEMPT_CODE = "2"
LOCAL_CURRENCY_CODE = "PES"


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
    account_id = fields.Many2one(
        "account.account",
        string="Account for created documents",
        check_company=True,
        domain="[('account_type', 'in', ('income', 'income_other'))]",
        help="Account of the lines of the documents this wizard creates.",
    )
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

    def _format_number(self, number):
        return "%05d-%08d" % (self.journal_id.l10n_ar_afip_pos_number, number)

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
        """Ask ARCA for every number of the range and propose what to do with each one."""
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
        serialized = {field: self._serialize(getattr(got, field, None)) for field in MATCH_FIELDS}
        serialized["Iva"] = [
            {"Id": str(item.Id), "BaseImp": float(item.BaseImp or 0)}
            for item in (getattr(getattr(got, "Iva", None), "AlicIva", None) or [])
        ]
        values = {
            "number": number,
            "date": datetime.strptime(str(got.CbteFch), "%Y%m%d").date(),
            "amount_total": float(got.ImpTotal or 0),
            "document_number": str(got.DocNro or ""),
            "auth_mode": got.EmisionTipo,
            "auth_code": str(got.CodAutorizacion),
            "auth_code_due": datetime.strptime(str(got.FchVto), "%Y%m%d").date(),
            "result": got.Resultado,
            "values": serialized,
            "action": "skip",
        }
        partner = self._find_partner(got)
        values["partner_id"] = partner.id
        draft = self._find_draft(got, partner, taken)
        if draft:
            values.update(move_id=draft.id, action="match")
            return values
        values["note"] = self._create_blocker(got, partner)
        if not values["note"]:
            values["action"] = "create"
        return values

    @api.model
    def _serialize(self, value):
        if value is None:
            return None
        return value if isinstance(value, (int, float, str)) else str(value)

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
        """The oldest draft of the journal with the same customer and total, not proposed for another number."""
        self.ensure_one()
        if not partner:
            return self.env["account.move"]
        drafts = self.env["account.move"].search(
            [
                ("journal_id", "=", self.journal_id.id),
                ("l10n_latam_document_type_id", "=", self.document_type_id.id),
                ("state", "=", "draft"),
                ("l10n_ar_afip_auth_code", "=", False),
                ("commercial_partner_id", "=", partner.commercial_partner_id.id),
                ("id", "not in", taken.ids),
            ],
            order="invoice_date, id",
        )
        total = float(got.ImpTotal or 0)
        return drafts.filtered(lambda m: not m.currency_id.compare_amounts(m.amount_total, total))[:1]

    def _create_blocker(self, got, partner):
        """Why this document cannot be created from what ARCA reports, if it cannot."""
        self.ensure_one()
        if not partner:
            return self.env._("No contact has the identification %s.", got.DocNro)
        if (got.MonId or LOCAL_CURRENCY_CODE) != LOCAL_CURRENCY_CODE:
            return self.env._("It is in foreign currency (%s): it can be assigned to a draft, not created.", got.MonId)
        if float(got.ImpTrib or 0):
            return self.env._("It has other taxes for %s, which have to be set by hand.", got.ImpTrib)
        return ""

    # ------------------------------------------------------------------ apply

    def action_apply(self):
        """Assign and create what is marked, from the lowest number up.

        Odoo numbers with its own sequence, so the numbers are taken in order: a skipped number stops the ones
        after it."""
        self.ensure_one()
        lines = self.line_ids.sorted("number")
        if lines.filtered(lambda line: line.action == "create") and not self.account_id:
            raise UserError(self.env._("Choose the account of the documents that are going to be created."))
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
            raise UserError(self.env._("No document is marked to assign or create."))
        done = self.env["account.move"]
        for line in todo:
            done |= line._apply()
        for line in todo.filtered("reverse"):
            line._reverse(line.applied_move_id)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Recovered documents"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", done.ids)],
        }

    def _sale_taxes_by_vat_code(self):
        """One sale tax per ARCA VAT code. With more than one the first is used: if it is not the right one the
        total does not match and the document is not created."""
        self.ensure_one()
        taxes = self.env["account.tax"].search(
            [
                ("company_id", "parent_of", self.company_id.id),
                ("type_tax_use", "=", "sale"),
                ("tax_group_id.l10n_ar_vat_afip_code", "!=", False),
            ],
            order="sequence, id",
        )
        by_code = {}
        for tax in taxes:
            by_code.setdefault(tax.tax_group_id.l10n_ar_vat_afip_code, tax)
        return by_code


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
    partner_id = fields.Many2one("res.partner", string="Customer")
    move_id = fields.Many2one(
        "account.move",
        string="Draft",
        domain="[('journal_id', '=', parent.journal_id), ('state', '=', 'draft')]",
    )
    applied_move_id = fields.Many2one("account.move", readonly=True)
    action = fields.Selection(
        [("match", "Assign"), ("create", "Create"), ("skip", "Skip")],
        required=True,
        default="skip",
    )
    reverse = fields.Boolean(
        "Neutralize",
        help="Issue the document that cancels it: a credit note for an invoice or a debit note, a debit note "
        "for a credit note. It is validated right away, so it asks ARCA for its own authorization.",
    )
    auth_mode = fields.Char(readonly=True)
    auth_code = fields.Char("CAE", readonly=True)
    auth_code_due = fields.Date("CAE due date", readonly=True)
    result = fields.Char(readonly=True)
    note = fields.Char(readonly=True)
    values = fields.Json(readonly=True)

    def _authorization_values(self):
        self.ensure_one()
        return {
            "l10n_ar_afip_auth_mode": self.auth_mode,
            "l10n_ar_afip_auth_code": self.auth_code,
            "l10n_ar_afip_auth_code_due": self.auth_code_due,
            "l10n_ar_afip_result": self.result,
        }

    def _apply(self):
        self.ensure_one()
        if self.action == "match":
            move = self.move_id
            if not move or move.state != "draft":
                raise UserError(self.env._("Number %s: the draft is no longer in draft.", self.number))
            move.sudo().write(dict(self._authorization_values(), invoice_date=self.date))
        else:
            move = self._create_move()
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
        move.message_post(
            body=self.env._(
                "Recovered from ARCA with the recovery wizard: number %(number)s, CAE %(cae)s.",
                number=self.number,
                cae=self.auth_code,
            )
        )
        self.applied_move_id = move
        return move

    def _create_move(self):
        self.ensure_one()
        wizard = self.wizard_id
        is_credit_note = wizard.document_type_id.internal_type == "credit_note"
        move = self.env["account.move"].create(
            dict(
                self._authorization_values(),
                move_type="out_refund" if is_credit_note else "out_invoice",
                partner_id=self.partner_id.id,
                journal_id=wizard.journal_id.id,
                invoice_date=self.date,
                l10n_latam_document_type_id=wizard.document_type_id.id,
                invoice_line_ids=[Command.create(values) for values in self._line_values()],
            )
        )
        if move.l10n_latam_document_type_id != wizard.document_type_id:
            raise UserError(
                self.env._(
                    "Number %(number)s: %(partner)s does not take %(document)s documents.",
                    number=self.number,
                    partner=self.partner_id.display_name,
                    document=wizard.document_type_id.display_name,
                )
            )
        if move.currency_id.compare_amounts(move.amount_total, self.amount_total):
            raise UserError(
                self.env._(
                    "Number %(number)s: built with a total of %(built)s and ARCA reports %(reported)s. Check the "
                    "sale taxes of the company before recovering it.",
                    number=self.number,
                    built=move.amount_total,
                    reported=self.amount_total,
                )
            )
        return move

    def _line_values(self):
        """One line per aliquot ARCA reported, plus what is not taxed and what is exempt."""
        self.ensure_one()
        values = self.values or {}
        taxes = self.wizard_id._sale_taxes_by_vat_code()
        label = self.env._("Document %s authorized by ARCA", self.wizard_id._format_number(self.number))
        buckets = [(item["Id"], item["BaseImp"]) for item in values.get("Iva") or []]
        buckets += [(NOT_TAXED_CODE, values.get("ImpTotConc")), (EXEMPT_CODE, values.get("ImpOpEx"))]
        lines = []
        for code, base in buckets:
            if not base or not float(base):
                continue
            tax = taxes.get(code)
            if not tax:
                raise UserError(self.env._("The company has no sale tax with the ARCA VAT code %s.", code))
            lines.append(
                {
                    "name": label,
                    "account_id": self.wizard_id.account_id.id,
                    "quantity": 1,
                    "price_unit": float(base),
                    "tax_ids": [Command.set(tax.ids)],
                }
            )
        if not lines:
            raise UserError(self.env._("ARCA reported no amounts for number %s.", self.number))
        return lines

    def _reverse(self, move):
        """The document that cancels the recovered one: a credit note for an invoice or a debit note, a debit
        note for a credit note. Odoo's own wizards pick its document type."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        reason = self.env._("Cancels %s, recovered from ARCA", move.name)
        ctx = {"active_model": "account.move", "active_ids": move.ids}
        if move.move_type == "out_refund":
            self.env["account.debit.note"].with_context(**ctx).create(
                {"date": today, "reason": reason, "copy_lines": True}
            ).create_debit()
            reverse = self.env["account.move"].search([("debit_origin_id", "=", move.id)], limit=1)
        else:
            reversal = (
                self.env["account.move.reversal"]
                .with_context(**ctx)
                .create({"journal_id": move.journal_id.id, "date": today, "reason": reason})
            )
            reversal.reverse_moves()
            reverse = reversal.new_move_ids
        if not reverse:
            raise UserError(self.env._("Could not build the document that cancels %s.", move.name))
        reverse.action_post()
        return reverse
