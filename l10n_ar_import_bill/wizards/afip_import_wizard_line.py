import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

# The CUIT is the only Argentinian document that lives in `vat`; every other one is an
# additional identifier of the contact.
AR_CUIT_IDENTIFIER_KEY = "AR_CUIT"

# What ARCA writes in the document type column and does not match an identifier key in
# 20.0. Everything else is resolved against the core metadata, by key.
ARCA_IDENTIFIER_ALIASES = {
    "pasaporte": "PASSPORT",
    "passport": "PASSPORT",
}

# Identifiers the listing cannot fill on its own: the CI derives its ARCA document type
# from the province, which ARCA does not export, and writing it without one raises and
# aborts the whole listing. The number goes to `vat`, like an unknown type does.
UNWRITABLE_IDENTIFIER_KEYS = ("AR_CI",)


class AfipImportWizardLine(models.TransientModel):
    _name = "afip.import.wizard.line"
    _description = "Invoice Line Imported from Excel"

    wizard_id = fields.Many2one("afip.import.wizard", required=True, ondelete="cascade")
    invoice_number = fields.Char()
    partner_name = fields.Char()
    partner_vat = fields.Char("Partner VAT")
    partner_identification_type = fields.Char("Identification Type")
    date_invoice = fields.Date("Invoice Date")
    currency = fields.Char()
    currency_rate = fields.Float("Exchange Rate")
    amount_total = fields.Float("Total")
    document_type = fields.Char()
    exists = fields.Boolean("Already Exists", compute="_compute_exists", store=True)
    neto_grav_iva_0 = fields.Float("Net Taxable VAT 0%")
    iva_2_5 = fields.Float("VAT 2.5%")
    neto_grav_iva_2_5 = fields.Float("Net Taxable VAT 2.5%")
    iva_5 = fields.Float("VAT 5%")
    neto_grav_iva_5 = fields.Float("Net Taxable VAT 5%")
    iva_10_5 = fields.Float("VAT 10.5%")
    neto_grav_iva_10_5 = fields.Float("Net Taxable VAT 10.5%")
    iva_21 = fields.Float("VAT 21%")
    neto_grav_iva_21 = fields.Float("Net Taxable VAT 21%")
    iva_27 = fields.Float("VAT 27%")
    neto_grav_iva_27 = fields.Float("Net Taxable VAT 27%")
    no_gravado = fields.Float(string="Non-Taxable")
    otros_tributos = fields.Float(string="Other Taxes")
    exento = fields.Float(string="Exempt")
    cae = fields.Char("CAE")

    @api.depends(
        "document_type",
        "invoice_number",
        "partner_vat",
        "partner_identification_type",
        # A repeated document is recognized by looking at the sibling lines, so removing
        # one line has to recompute the rest: otherwise deleting the first of two equal
        # lines leaves the second marked as already in, and it is never created.
        "wizard_id.line_ids",
        "wizard_id.journal_id.type",
        "wizard_id.company_id",
    )
    def _compute_exists(self):
        identifiers = {line.id: line._get_identifier() for line in self | self.wizard_id.line_ids}
        repeated = self._repeated_lines(identifiers)
        partners_by_document = {}
        for line in self:
            if line.id in repeated:
                line.exists = True
                continue

            # Determine move types based on journal type
            if line.wizard_id.journal_id.type == "sale":
                move_types = ["out_refund", "out_invoice"]
            else:
                move_types = ["in_refund", "in_invoice"]

            existing_invoice = line._existing_invoices(move_types, identifiers, partners_by_document)

            line.exists = bool(existing_invoice)

    def _repeated_lines(self, identifiers):
        """The lines whose document already came in an earlier line of the same wizard.

        Two exports with overlapping months bring the same document twice. The first
        line creates the invoice, so the next ones are as already in as the invoices on
        file: they are shown and skipped instead of being dropped on the way in.
        """
        repeated = set()
        for wizard in self.wizard_id:
            seen = set()
            for line in wizard.line_ids:
                key = line._document_key(identifiers[line.id])
                if key in seen:
                    repeated.add(line.id)
                else:
                    seen.add(key)
        return repeated

    def _existing_invoices(self, move_types, identifiers, partners_by_document):
        """The invoices already on file for this line's document."""
        self.ensure_one()
        identifier = identifiers[self.id]
        # The name only joins the key when there is no document: otherwise two lines of
        # the same supplier with the name spelled differently would resolve twice.
        cache_key = identifier if identifier[1] else (*identifier, self._partner_name_key())
        if cache_key not in partners_by_document:
            # An ARCA listing repeats the same supplier on many lines, and resolving one
            # document costs a couple of queries: it is resolved once per supplier.
            partners_by_document[cache_key] = self._find_partners(identifier)
        partners = partners_by_document[cache_key]
        if not partners:
            return self.env["account.move"]

        candidates = self.env["account.move"].search(
            [
                ("move_type", "in", move_types),
                ("display_name", "ilike", self.invoice_number),
                # Every contact carrying the document, not just the first one: a
                # duplicated contact still has to recognize its own invoices.
                ("partner_id", "in", partners.ids),
                ("company_id", "=", self.wizard_id.company_id.id),
            ]
        )
        # `display_name` narrows the search in SQL, but it also carries the reference,
        # where a credit note names the invoice it cancels. The document number is what
        # decides whether this very invoice is already in.
        return candidates.filtered(lambda move: move.l10n_latam_document_number == self.invoice_number)

    def _document_key(self, identifier=None):
        """What makes two lines the same document.

        The document type is part of it: an invoice and its credit note share the point
        of sale and the number, and they are two different documents.
        """
        self.ensure_one()
        # The normalized document, not the one the listing brings: the same number
        # written with dots in one export and without them in the other is one document.
        key, value = identifier if identifier is not None else self._get_identifier()
        return (self.document_type, self.invoice_number, key or "", value or self._partner_name_key())

    def _partner_name_key(self):
        """The contact name as it is matched: ARCA writes it in upper case."""
        self.ensure_one()
        return (self.partner_name or "").strip().lower()

    def _get_identifier_key(self):
        """ARCA names the document type ("CUIT", "DNI", "Pasaporte"). Up to 19.0 that was a
        record of the LatAm catalog; in 20.0 the CUIT travels in `vat` and every other
        document is an additional identifier of the contact.

        The match is against identifier keys, never their labels: a label is translated
        and would map the same file differently depending on who imports it.
        """
        self.ensure_one()
        name = (self.partner_identification_type or "").strip().lower()
        if not name:
            return None
        if name == "cuit":
            return AR_CUIT_IDENTIFIER_KEY
        if name in ARCA_IDENTIFIER_ALIASES:
            return ARCA_IDENTIFIER_ALIASES[name]
        # The contact metadata mixes the core keys with the Argentinian ones, so both
        # PASSPORT and AR_DNI come through here; ARCA writes the acronym, with no prefix.
        for key in self.env["res.partner"]._get_all_additional_identifiers_metadata():
            if key.lower() == name or key.lower().removeprefix("ar_") == name:
                return key
        return None

    def _get_identifier(self):
        """This line's document as 20.0 stores it, as a ``(key, value)`` pair.

        The lookup and the creation go through this same normalization, so the contact
        created from one listing is the one the next listing finds: 20.0 compacts what it
        stores ("30.123.456" becomes "30123456") and an exact match on the raw number
        would never find it again.

        A `key` of None means the number goes to `vat` untouched, the way 19.0 stored it:
        either the type is not one 20.0 knows, or the number is not a valid document of
        that type. Rejecting it instead would abort a whole listing over one line.
        """
        self.ensure_one()
        value = (self.partner_vat or "").strip()
        if not value:
            return None, None
        key = self._get_identifier_key()
        if key == AR_CUIT_IDENTIFIER_KEY:
            normalized, _country_code = self.env["res.partner"]._run_vat_checks(
                self.env.ref("base.ar"), value, validation="setnull"
            )
            return (key, normalized) if normalized else (None, value)
        if key in UNWRITABLE_IDENTIFIER_KEYS:
            return None, value
        if key:
            validation = self.env["res.partner"]._validate_identifier(key, value)
            return (key, validation["value"]) if validation["valid"] else (None, value)
        return None, value

    def _find_partners(self, identifier=None):
        """Every contact carrying this line's document, or an empty recordset.

        Like in 19.0 the search is not scoped to the company, and it returns all the
        matches: the module creates the contact when there is none, and the caller that
        needs a single one takes the first. `identifier` is the pair `_get_identifier`
        returns, passed in when the caller already resolved it.
        """
        self.ensure_one()
        key, value = identifier if identifier is not None else self._get_identifier()
        if not value:
            # No document on the line: the name is the only thing left to match on, and
            # matching nothing would create a new contact on every import. 19.0 matched
            # any contact without a VAT, which attached the invoice to an arbitrary one.
            # ARCA writes the name in upper case, so the match ignores case, and it only
            # reaches contacts with no document at all — the ones this path creates.
            if not self.partner_name:
                return self.env["res.partner"]
            pattern = self.partner_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            return self.env["res.partner"].search(
                [("name", "=ilike", pattern), ("vat", "=", False), ("additional_identifiers", "=", False)]
            )
        if not key or key == AR_CUIT_IDENTIFIER_KEY:
            return self.env["res.partner"].search([("vat", "=", value)])
        # A Json field supports no domain operator, so the containment goes as SQL, the
        # way the core looks a contact up by its identifiers: it uses the jsonb index
        # instead of scanning the serialized text of every contact.
        partner = self.env["res.partner"]
        query = partner._search([])
        query.add_where(
            SQL(
                "%s @> %s::jsonb",
                partner._field_to_sql(partner._table, "additional_identifiers"),
                json.dumps({key: value}),
            )
        )
        partners = partner.browse(list(query))
        # The 19.0 importer kept a personal document in `vat`: on a base that has just
        # been upgraded those contacts are still there, and they are the same contact.
        return partners or partner.search([("vat", "=", value)])

    def _find_partner(self, identifier=None):
        """The first contact carrying this line's document, or an empty recordset."""
        self.ensure_one()
        return self._find_partners(identifier)[:1]

    def _get_partner_by_vat(self):
        """The contact for this line, created if no one carries its document yet."""
        self.ensure_one()

        identifier = self._get_identifier()
        partner = self._find_partner(identifier)

        if not partner:
            key, value = identifier
            if not value and not self.partner_name:
                raise UserError(
                    _(
                        "The line of invoice %s has neither a document nor a name for the contact, "
                        "so the contact cannot be identified. Complete it in the ARCA file and import again.",
                        self.invoice_number or "",
                    )
                )
            vals = {"name": self.partner_name}
            if key == AR_CUIT_IDENTIFIER_KEY:
                # The country is what makes 20.0 read the number as a CUIT: the AFIP code
                # and the contact being a company both come from it.
                vals["vat"] = value
                vals["country_id"] = self.env.ref("base.ar").id
            elif key:
                # A personal document and a CUIT cannot live on the same partner in 20.0.
                vals["additional_identifiers"] = {key: value}
            else:
                # No recognizable type, or a number 20.0 does not accept as that document:
                # it goes where it went in 19.0, and the country is not made up, so Odoo
                # does not validate it and the contact can be corrected by hand.
                vals["vat"] = value

            partner = self.env["res.partner"].create(vals)

        return partner

    def _get_document_type(self):
        """The `l10n_latam.document.type` of this line, by the code the listing brings."""
        self.ensure_one()
        # Extract the number before the hyphen
        invoice_type_code = self.document_type.split(" - ")[0].strip()

        # Search for the document type in the model l10n_latam.document.type
        document_type = self.env["l10n_latam.document.type"].search(
            [("code", "=", invoice_type_code), ("country_id.code", "=", "AR")], limit=1
        )

        if not document_type:
            raise UserError(_("No document type found for code: %s") % invoice_type_code)

        return document_type

    def _get_currency(self):
        """The currency of this line, by the name or the symbol the listing brings."""
        # Extract the number before the hyphen
        if self.currency == "$":
            currency_id = self.env["res.currency"].search([("name", "=", "ARS")], limit=1)
        else:
            currency_id = self.env["res.currency"].search(
                ["|", ("name", "=", self.currency), ("symbol", "=", self.currency)], limit=1
            )

        if not currency_id:
            raise UserError(_("No currency found for code: %s") % self.currency)

        return currency_id

    def _get_move_type(self):
        """The move type for this line, from its document type and the journal."""
        move_type = False
        document_type = self._get_document_type()
        is_sale = self.wizard_id.journal_id.type == "sale"

        if document_type.internal_type in ["invoice", "debit_note"]:
            move_type = "out_invoice" if is_sale else "in_invoice"
        elif document_type.internal_type == "credit_note":
            move_type = "out_refund" if is_sale else "in_refund"
        return move_type

    def _neto_gravado(self, vat_rate, vat_amount, neto_amount):
        """The taxable net for one VAT rate.

        ARCA sometimes brings the VAT amount with the taxable net column empty; deriving
        the net from the amount is the only way not to drop that part of the invoice.
        """
        if neto_amount > 0 or not vat_amount or not vat_rate:
            return neto_amount
        return round(vat_amount / (vat_rate / 100), 2)

    def _neto_sin_iva(self):
        """Neto a imputar como costo sin IVA: el total menos "Otros Tributos"
        (que se agregan aparte con el wizard de impuestos). Se usa tanto en el
        fallback de RI como en el flujo de Exento / Monotributo."""
        self.ensure_one()
        base_amount = self.amount_total
        if self.otros_tributos > 0:
            base_amount -= self.otros_tributos
        return base_amount

    def _create_line(self, price_unit, tax_ids):
        """The command that adds one invoice line with its amount and its taxes.

        The contact is not written here: the line takes it from the invoice, and writing
        it again lets the two drift apart.
        """
        vals = {
            "name": _("Created by invoice import"),
            "quantity": 1.0,
            "price_unit": price_unit,
            "tax_ids": [(6, 0, tax_ids)],
        }
        return (0, 0, vals)

    def action_remove(self):
        wizard = self.mapped("wizard_id")
        self.unlink()
        # Re-open the same wizard in a modal to refresh only its content (lines)
        view = self.env.ref("l10n_ar_import_bill.view_afip_import_wizard_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "res_model": "afip.import.wizard",
            "res_id": wizard.id if wizard else False,
            "view_mode": "form",
            "target": "new",
            # Without it the initial setup flow loses `initial_setup`, and with it the
            # counterpart account and the accounting start date check.
            "context": dict(self.env.context),
        }
        if view:
            action.update({"view_id": view.id, "views": [(view.id, "form")]})
        return action
