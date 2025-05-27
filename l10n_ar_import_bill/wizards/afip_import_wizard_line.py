from odoo import models, fields
from odoo.exceptions import UserError


class AfipImportWizardLine(models.TransientModel):
    _name = "afip.import.wizard.line"
    _description = "Línea de Factura Importada desde Excel"

    wizard_id = fields.Many2one("afip.import.wizard", required=True, ondelete="cascade")
    invoice_number = fields.Char("Número de Factura")
    partner_name = fields.Char("Proveedor")
    partner_vat = fields.Char("VAT del Proveedor")
    partner_identification_type = fields.Char("Tipo de Identificación")
    date_invoice = fields.Date("Fecha de Factura")
    currency = fields.Char("Moneda")
    amount_total = fields.Float("Total")
    document_type = fields.Char(string="Tipo de Documento")
    move_type = fields.Char(string="Tipo de Factura")
    exists = fields.Boolean("Ya Existe", compute="_compute_exists", store=True)
    neto_gravado = fields.Float("Impuesto Neto Gravado")
    no_gravado = fields.Float("No Gravado")
    otros_tributos = fields.Float("Otros Tributos")
    exento = fields.Float("Exento")
    iva = fields.Float("IVA")
    cae = fields.Char("CAE")

    def _compute_exists(self):
        for line in self:
            existing_invoice = line.env["account.move"].search([
                    ("move_type", "=", "in_invoice"),
                    ("display_name", "ilike", line.invoice_number),
                    ("partner_id.vat", "=", line.partner_vat)
                ], limit=1)
            line.exists = bool(existing_invoice)

    def _get_partner_by_vat(self):
        """
        Busca el proveedor en la tabla de proveedores
        :param vat: CUIT del proveedor
        :return: id del proveedor
        """
        self.ensure_one()

        partner = self.env['res.partner'].search([('vat', '=', self.partner_vat)], limit=1)

        if not partner:
            identification_type = self.env['l10n_latam.identification.type'].search([
                ('name', 'ilike', self.partner_identification_type)
            ], limit=1)

            partner = self.env['res.partner'].create({
                'name': self.partner_name,
                'vat': self.partner_vat,
                'l10n_latam_identification_type_id': identification_type.id,
                'company_type': 'company',
            })
            # Si el tipo de identificación es CUIT (código AFIP 80), actualizamos los datos desde AFIP
            if partner.l10n_latam_identification_type_id.l10n_ar_afip_code == 80:
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
        document_type = self.env['l10n_latam.document.type'].search([('code', '=', invoice_type_code)], limit=1)

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
            currency_id = self.env['res.currency'].search([('name', '=', 'ARS')], limit=1)
        else:
            currency_id = self.env['res.currency'].search([('name', '=', self.currency)], limit=1)

        if not currency_id:
            raise UserError(_("No currency found for code: %s") % currency_id)

        return currency_id

    def _get_move_type(self):
        """
        Compute the move_type based on the document type.
        :return: None
        """
        move_type = False
        document_type = self._get_document_type()
        if document_type.internal_type in ["invoice", "debit_note"]:
            move_type = 'in_invoice'
        elif document_type.internal_type == "credit_note":
            move_type = 'in_refund'
        return move_type
