from markupsafe import Markup
from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError


class AfipImportWizard(models.TransientModel):
    _name = 'afip.import.wizard'
    _description = 'Import AFIP bills from xlsx'

    _description = "Importador de Facturas de Proveedor desde Excel AFIP"

    line_ids = fields.One2many(
        "afip.import.wizard.line",
        "wizard_id",
        string="Líneas de Facturas"
    )
    company_id = fields.Many2one('res.company', required=True)
    journal_id = fields.Many2one('account.journal', required=True)

    def action_confirm(self):
        moves = self.env['account.move']
        for line in self.line_ids.filtered(lambda l: not l.exists):

            partner = self._get_partner_by_vat(line.partner_vat)

            document_type = self._get_invoice_type(line.document_type)

            currency = self._get_currency(line.currency)

            move_vals = {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": line.date_invoice,
                "ref": line.invoice_number,
                "currency_id": self.env.company.currency_id.id,  # asumiendo pesos
                "l10n_latam_document_type_id": document_type.id,
                "journal_id": self.journal_id.id,
                "company_id": self.company_id.id,
            }
            move = self.env["account.move"].create(move_vals)
            moves += move

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": [("id", "in", moves.ids)],
            "target": "current",
        }

    def _get_partner_by_vat(self, vat):
        """
        Busca el proveedor en la tabla de proveedores
        :param vat: CUIT del proveedor
        :return: id del proveedor
        """

        # Search for the partner in the model res.partner
        partner = self.env['res.partner'].search([('vat', '=', vat)], limit=1)

        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.partner_name,
                'vat': vat,
                'company_type': 'company',
            })

        return partner

    def _get_invoice_type(self, invoice_type):

        """
        Busca el tipo de factura en la tabla de tipos de documento
        :param invoice_type: Tipo de factura (A, B, C, etc)
        :return: id del tipo de documento
        """
        # Extract the number before the hyphen
        invoice_type_code = invoice_type.split(" - ")[0].strip()

        # Search for the document type in the model l10n_latam.document.type
        document_type = self.env['l10n_latam.document.type'].search([('code', '=', invoice_type_code)], limit=1)

        if not document_type:
            raise UserError(_("No document type found for code: %s") % invoice_type_code)

        return document_type

    def _get_currency(self, currency):
        """
        Busca la moneda en la tabla de monedas
        :param currency: Moneda (ARS, USD, etc)
        :return: id de la moneda
        """
        # Extract the number before the hyphen
        if currency == "$":
            currency_id = self.env['res.currency'].search([('name', '=', 'ARS')], limit=1)
        else:
            currency_id = self.env['res.currency'].search([('name', '=', currency)], limit=1)

        if not currency_id:
            raise UserError(_("No currency found for code: %s") % currency_id)

        return currency_id
