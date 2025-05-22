from odoo import models, fields


class AfipImportWizardLine(models.TransientModel):
    _name = "afip.import.wizard.line"
    _description = "Línea de Factura Importada desde Excel"

    wizard_id = fields.Many2one("afip.import.wizard", required=True, ondelete="cascade")
    invoice_number = fields.Char("Número de Factura")
    partner_name = fields.Char("Proveedor")
    partner_vat = fields.Char("CUIT del Proveedor")
    date_invoice = fields.Date("Fecha de Factura")
    currency = fields.Char("Moneda")
    amount_total = fields.Float("Total")
    document_type_id = fields.Many2one("l10n_ar.document.type", string="Tipo de Documento")
    exists = fields.Boolean("Ya Existe", compute="_compute_exists", store=True)

    def _compute_exists(self):
        for line in self:
            existing_invoice = line.env["account.move"].search([
                    ("move_type", "=", "in_invoice"),
                    ("display_name", "ilike", line.invoice_number),
                    ("partner_id.vat", "=", line.partner_vat)
                ], limit=1)
            line.exists = bool(existing_invoice)
