import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

# Lo que ARCA escribe en la columna del tipo de documento y no coincide con la clave
# del identificador en 20. El resto sale de la metadata del core, por clave.
ARCA_IDENTIFIER_ALIASES = {
    "pasaporte": "PASSPORT",
    "passport": "PASSPORT",
}


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
    move_type = fields.Char(string="Invoice Type")
    exists = fields.Boolean("Already Exists", compute="_compute_exists", store=True)
    iva_0 = fields.Float("VAT 0%")
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

    @api.depends("invoice_number", "partner_vat")
    def _compute_exists(self):
        # Un listado de ARCA repite el mismo proveedor en muchas líneas: sin esto,
        # resolverlo sería una consulta por línea.
        partners = {}
        for line in self:
            # Determine move types based on journal type
            if line.wizard_id.journal_id.type == "sale":
                move_types = ["out_refund", "out_invoice"]
            else:
                move_types = ["in_refund", "in_invoice"]

            cache_key = (line._get_identifier_key(), line.partner_vat)
            if cache_key not in partners:
                partners[cache_key] = line._find_partner()
            partner = partners[cache_key]
            if not partner:
                line.exists = False
                continue

            existing_invoice = line.env["account.move"].search(
                [
                    ("move_type", "in", move_types),
                    ("display_name", "ilike", line.invoice_number),
                    ("partner_id", "=", partner.id),
                    ("company_id", "=", line.wizard_id.company_id.id),
                ],
                limit=1,
            )

            line.exists = bool(existing_invoice)

    def _get_identifier_key(self):
        """ARCA nombra el tipo de documento ("CUIT", "DNI", "Pasaporte"). Hasta la 19 eso
        era un registro del catálogo LatAm; en 20 el CUIT viaja en `vat` y los demás
        documentos son identificadores adicionales del contacto.

        The match is against identifier keys, never their labels: a label is translated
        and would map the same file differently depending on who imports it.
        """
        self.ensure_one()
        name = (self.partner_identification_type or "").strip().lower()
        if not name:
            return None
        if name == "cuit":
            return "AR_CUIT"
        if name in ARCA_IDENTIFIER_ALIASES:
            return ARCA_IDENTIFIER_ALIASES[name]
        # La metadata del contacto mezcla las claves del core con las argentinas, así que
        # acá entran tanto PASSPORT como AR_DNI; ARCA escribe la sigla, sin el prefijo.
        for key in self.env["res.partner"]._get_all_additional_identifiers_metadata():
            if key.lower() == name or key.lower().removeprefix("ar_") == name:
                return key
        return None

    def _find_partner(self):
        """El contacto que ya tiene el documento de esta línea, o vacío.

        Los dos caminos buscan igual que en 19.0: el primero que tenga ese documento,
        sin filtrar por compañía. An `additional_identifiers` lookup needs raw SQL
        because a Json field cannot be searched through a domain.
        """
        self.ensure_one()
        identifier_key = self._get_identifier_key()
        if not identifier_key or identifier_key == "AR_CUIT":
            return self.env["res.partner"].search([("vat", "=", self.partner_vat)], limit=1)

        partners = self.env["res.partner"]
        query = partners._search([("active", "=", True)], limit=1)
        query.add_where(
            SQL(
                "%s @> %s::jsonb",
                partners._field_to_sql(partners._table, "additional_identifiers"),
                json.dumps({identifier_key: self.partner_vat}),
            )
        )
        return partners.browse(query)

    def _get_partner_by_vat(self):
        """
        Busca el proveedor en la tabla de proveedores
        :param vat: CUIT del proveedor
        :return: id del proveedor
        """
        self.ensure_one()

        partner = self._find_partner()

        if not partner:
            identifier_key = self._get_identifier_key()
            vals = {"name": self.partner_name}
            if identifier_key == "AR_CUIT":
                # El país es lo que hace que 20 lea el número como CUIT: de ahí salen
                # el código de AFIP y que el contacto quede como compañía.
                vals["vat"] = self.partner_vat
                vals["country_id"] = self.env.ref("base.ar").id
            elif identifier_key:
                # A personal document and a CUIT cannot live on the same partner in 20.0.
                vals["additional_identifiers"] = {identifier_key: self.partner_vat}
            else:
                # Sin tipo reconocible el número va donde iba en 19.0, y el país no se
                # inventa: un proveedor del exterior no es argentino.
                vals["vat"] = self.partner_vat

            partner = self.env["res.partner"].create(vals)
            # Si el tipo de identificación es CUIT (código AFIP 80), actualizamos los datos desde AFIP
            # The code is text and this compares it to a number, so it never matches: kept as it
            # was in 19.0, where the AFIP lookup was already dead. Turning it on is a decision.
            if partner.l10n_ar_afip_code == 80:
                partner.button_update_partner_data_from_afip()

        return partner

    def _get_document_type(self):
        """
        Busca el tipo de factura en la tabla de tipos de documento
        :param invoice_type: Tipo de factura (A, B, C, etc)
        :return: id del tipo de documento
        """
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
        """
        Busca la moneda en la tabla de monedas
        :param currency: Moneda (ARS, USD, etc)
        :return: id de la moneda
        """
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
        """
        Compute the move_type based on the document type and journal type.
        :return: move_type string
        """
        move_type = False
        document_type = self._get_document_type()
        is_sale = self.wizard_id.journal_id.type == "sale"

        if document_type.internal_type in ["invoice", "debit_note"]:
            move_type = "out_invoice" if is_sale else "in_invoice"
        elif document_type.internal_type == "credit_note":
            move_type = "out_refund" if is_sale else "in_refund"
        return move_type

    def _neto_sin_iva(self):
        """Neto a imputar como costo sin IVA: el total menos "Otros Tributos"
        (que se agregan aparte con el wizard de impuestos). Se usa tanto en el
        fallback de RI como en el flujo de Exento / Monotributo."""
        self.ensure_one()
        base_amount = self.amount_total
        if self.otros_tributos > 0:
            base_amount -= self.otros_tributos
        return base_amount

    # Definimos la funcion que crea las lineas de factura
    # con el precio unitario y los impuestos correspondientes

    def _create_line(self, price_unit, tax_ids):
        partner = self._get_partner_by_vat()
        vals = {
            "name": _("Created by invoice import"),
            "quantity": 1.0,
            "price_unit": price_unit,
            "tax_ids": [(6, 0, tax_ids)],
            "partner_id": partner.id,
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
        }
        if view:
            action.update({"view_id": view.id, "views": [(view.id, "form")]})
        return action
