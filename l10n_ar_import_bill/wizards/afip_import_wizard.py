from markupsafe import Markup
from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


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
            partner = self.env['res.partner'].search([("vat", "=", line.partner_vat)], limit=1)
            if not partner:
                raise ValidationError(f"No se encontró un partner con CUIT {line.partner_vat}")

            move_vals = {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": line.date_invoice,
                "ref": line.invoice_number,
                "currency_id": self.env.company.currency_id.id,  # asumiendo pesos
                "invoice_line_ids": [(0, 0, {
                    "name": "Factura AFIP",
                    "price_unit": line.amount_total,
                    "quantity": 1,
                })],
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
