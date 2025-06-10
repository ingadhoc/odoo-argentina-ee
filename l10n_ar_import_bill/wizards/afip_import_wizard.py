import math

from odoo import fields, models

# from odoo.exceptions import ValidationError


class AfipImportWizard(models.TransientModel):
    _name = "afip.import.wizard"
    _description = "Import AFIP bills from xlsx"

    _description = "Importador de Facturas de Proveedor desde Excel AFIP"

    line_ids = fields.One2many("afip.import.wizard.line", "wizard_id", string="Líneas de Facturas")
    company_id = fields.Many2one("res.company", required=True)
    journal_id = fields.Many2one("account.journal", required=True)

    def action_confirm(self):
        new_moves = self.env["account.move"]
        iva_no_corresponde = self.env.ref(f"account.{self.company_id.id}_ri_tax_vat_no_corresponde_compras")
        iva_no_gravado = self.env.ref(f"account.{self.company_id.id}_ri_tax_vat_no_gravado_compras")
        iva_tax_ids = {iva_no_corresponde.id, iva_no_gravado.id}

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
                "line_ids": [],
            }

            def create_line(price_unit, tax_ids):
                return (
                    0,
                    0,
                    {
                        "name": "Creado por importación de facturas",
                        "quantity": 1.0,
                        "price_unit": price_unit,
                        "tax_ids": [(6, 0, tax_ids)],
                        "partner_id": partner.id,
                    },
                )

            if not math.isnan(line.iva) and line.iva > 0:
                calculated_tax = round(line.iva * 100 / line.neto_gravado, 1)
                tax = self.env["account.tax"].search(
                    [
                        ("company_id", "=", self.company_id.id),
                        ("amount", "=", calculated_tax),
                        ("type_tax_use", "=", "purchase"),
                    ],
                    limit=1,
                )

                if tax:
                    iva_tax_ids.add(tax.id)
                    move_vals["line_ids"].append(create_line(line.neto_gravado, [tax.id]))

            tax_zero_id = iva_no_corresponde.id if document_type.l10n_ar_letter == "C" else iva_no_gravado.id

            if math.isnan(line.no_gravado) or line.no_gravado <= 0:
                move_vals["line_ids"].append(create_line(line.amount_total, [tax_zero_id]))
            if line.no_gravado > 0:
                move_vals["line_ids"].append(create_line(line.no_gravado, [tax_zero_id]))

            # IF DEL AUTORIZATION CODE IS NOT EMPTY, ADD IT TO THE MOVE

            move = self.env["account.move"].create(move_vals)
            new_moves += move

        new_moves.filtered(lambda m: any(tax.id in iva_tax_ids for tax in m.line_ids.mapped("tax_ids"))).action_post()

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "name": "Facturas de Proveedor Importadas",
            "domain": [("id", "in", new_moves.ids)],
            "target": "current",
        }
