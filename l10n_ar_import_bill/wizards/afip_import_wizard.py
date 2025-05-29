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

            partner = line._get_partner_by_vat()

            document_type = line._get_document_type()

            currency = line._get_currency()
            move_type = line._get_move_type()

            move_vals = {
                "move_type": move_type,
                "l10n_latam_document_type_id": document_type.id,
                "partner_id": partner.id,
                "invoice_date": line.date_invoice,
                "l10n_latam_document_number": line.invoice_number,
                "currency_id": currency.id,  # asumiendo pesos
                "invoice_currency_rate": line.currency_rate,  # asumiendo pesos
                "journal_id": self.journal_id.id,
                "company_id": self.company_id.id,
            }

            # IF DEL AUTORIZATION CODE IS NOT EMPTY, ADD IT TO THE MOVE

            move = self.env["account.move"].create(move_vals)
            moves += move

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
            "target": "current",
        }
