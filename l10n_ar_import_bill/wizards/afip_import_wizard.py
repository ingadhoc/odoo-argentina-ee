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
        tax_iva_no_corresponde = self.env.ref(f"account.{self.company_id.id}_ri_tax_vat_no_corresponde_compras")
        tax_iva_no_gravado = self.env.ref(f"account.{self.company_id.id}_ri_tax_vat_no_gravado_compras")
        tax_otros_tributos = self.env.ref(f"account.{self.company_id.id}_base_tax_otros_tributos")
        iva_tax_ids = {tax_iva_no_corresponde.id, tax_iva_no_gravado.id}

        for line in self.line_ids.filtered(lambda l: not l.exists):
            partner = line._get_partner_by_vat()

            document_type = line._get_document_type()

            currency = line._get_currency()
            move_type = line._get_move_type()

            tax_zero_id = tax_iva_no_corresponde.id if document_type.l10n_ar_letter == "C" else tax_iva_no_gravado.id

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

            # Agregamos la linea de IVA.
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
                # Si encuentra un IVA correspondiente al porcentaje lo agrega a la factura.
                if tax:
                    iva_tax_ids.add(tax.id)
                    move_vals["line_ids"].append(line._create_line(line.neto_gravado, [tax.id]))

            # Si no encuentra IVA ni importe "No Gravado" agrega la linea como "IVA No Corresponde" o "IVA No Gravado" dependiendo del tipo de documento.
            elif math.isnan(line.no_gravado) or line.no_gravado <= 0:
                move_vals["line_ids"].append(
                    line._create_line(line.amount_total - int(line.otros_tributos), [tax_zero_id])
                )

            if line.no_gravado > 0:
                move_vals["line_ids"].append(line._create_line(line.no_gravado, [tax_zero_id]))

            if line.otros_tributos > 0:
                move_vals["line_ids"].append(line._create_line(line.otros_tributos, [tax_otros_tributos.id]))

            move = self.env["account.move"].create(move_vals)
            new_moves += move

        # Filtramos para postear las facturas que tienen lineas de IVA
        # y no tienen el impuesto de otros tributos, ya que este impuesto
        # requiere manipulacion del usuario
        moves_to_post = new_moves.filtered(
            lambda m: any(tax.id in iva_tax_ids for tax in m.line_ids.mapped("tax_ids"))
            and not any(tax.id == tax_otros_tributos.id for tax in m.line_ids.mapped("tax_ids"))
        )
        moves_to_post.action_post()

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "name": "Facturas de Proveedor Importadas",
            "domain": [("id", "in", new_moves.ids)],
            "target": "current",
        }
