import math

from odoo import fields, models
from odoo.exceptions import UserError


class AfipImportWizard(models.TransientModel):
    _name = "afip.import.wizard"
    _description = "Import AFIP bills from xlsx"

    _description = "Importador de Facturas de Proveedor desde Excel AFIP"

    line_ids = fields.One2many("afip.import.wizard.line", "wizard_id", string="Líneas de Facturas")
    company_id = fields.Many2one("res.company", required=True)
    journal_id = fields.Many2one("account.journal", required=True)
    total_bills_to_create = fields.Integer(
        compute="_compute_bills_to_create",
        string="Total de Facturas a Crear",
    )
    total_bills_exists = fields.Integer(
        compute="_compute_bills_exists",
        string="Total de Facturas Existentes",
    )

    def _compute_bills_to_create(self):
        self.total_bills_to_create = len(self.line_ids.filtered(lambda l: not l.exists))

    def _compute_bills_exists(self):
        self.total_bills_exists = len(self.line_ids.filtered(lambda l: l.exists))

    def action_confirm(self):
        if all(line.exists for line in self.line_ids):
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Import completed",
                    "message": "No invoices were created: all required invoices already exist.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        new_moves = self.env["account.move"]
        base_domain = [
            ("price_include", "=", False),
            ("company_id", "=", self.company_id.id),
            ("type_tax_use", "=", "purchase"),
        ]
        tax_iva_no_corresponde = self.env["account.tax"].search(
            base_domain + [("tax_group_id.l10n_ar_vat_afip_code", "=", "0")], limit=1
        )
        tax_iva_no_gravado = self.env["account.tax"].search(
            base_domain + [("tax_group_id.l10n_ar_vat_afip_code", "=", "1")], limit=1
        )
        tax_otros_tributos = self.env["account.tax"].search(
            base_domain + [("tax_group_id.l10n_ar_tribute_afip_code", "=", "99")], limit=1
        )
        tax_iva_exento = self.env["account.tax"].search(
            base_domain + [("tax_group_id.l10n_ar_vat_afip_code", "=", "2")], limit=1
        )

        iva_tax_ids = {tax_iva_no_corresponde.id, tax_iva_no_gravado.id, tax_iva_exento.id}

        for line in self.line_ids.filtered(lambda l: not l.exists):
            partner = line._get_partner_by_vat()

            document_type = line._get_document_type()

            currency = line._get_currency()
            move_type = line._get_move_type()

            tax_zero_id = tax_iva_no_corresponde if document_type.l10n_ar_letter in ["C", "B"] else tax_iva_no_gravado

            move_vals = {
                "move_type": move_type,
                "l10n_latam_document_type_id": document_type.id,
                "partner_id": partner.id,
                "invoice_date": line.date_invoice,
                "l10n_latam_document_number": line.invoice_number,
                "currency_id": currency.id,
                "journal_id": self.journal_id.id,
                "company_id": self.company_id.id,
                "l10n_ar_afip_auth_code": line.cae,
                "line_ids": [],
            }

            # Agregamos la linea con IVA y otros tributos (si existen).
            taxes_in_line_ids = []
            if not math.isnan(line.iva) and line.iva > 0:
                calculated_tax = round(line.iva * 100 / line.neto_gravado, 1)
                iva_tax = self.env["account.tax"].search(
                    base_domain
                    + [
                        ("amount", "=", calculated_tax),
                        ("tax_group_id.l10n_ar_vat_afip_code", "!=", False),
                    ],
                    limit=1,
                )
                # Si encuentra un IVA correspondiente al porcentaje lo agrega a la factura.
                if iva_tax:
                    iva_tax_ids.add(iva_tax.id)
                    taxes_in_line_ids.append(iva_tax.id)

                # Si encuentra otros tributos, los agrega a la factura.
                if line.otros_tributos > 0:
                    if not tax_otros_tributos:
                        raise UserError(
                            "No se encontró un impuesto de Otros Tributos. "
                            "Debe crear un impuesto de compras con el grupo 'Otros Tributos'."
                        )
                    taxes_in_line_ids.append(tax_otros_tributos.id)

                if taxes_in_line_ids:
                    move_vals["line_ids"].append(line._create_line(line.neto_gravado, taxes_in_line_ids))

            # Si no encuentra IVA ni importe "No Gravado" agrega la linea como "IVA No Corresponde" o "IVA No Gravado" dependiendo del tipo de documento.
            elif math.isnan(line.no_gravado) or line.no_gravado <= 0 and line.exento <= 0 or math.isnan(line.exento):
                if not tax_zero_id and document_type.l10n_ar_letter in ["C", "B"]:
                    raise UserError(
                        "No se encontró un impuesto de IVA No Corresponde. "
                        "Debe crear un impuesto de compras con el grupo 'IVA No Corresponde'."
                    )
                elif not tax_zero_id:
                    raise UserError(
                        "No se encontró un impuesto de IVA No Gravado. "
                        "Debe crear un impuesto de compras con el grupo 'IVA No Gravado'."
                    )

                move_vals["line_ids"].append(
                    line._create_line(line.amount_total - int(line.otros_tributos), [tax_zero_id.id])
                )

            if line.exento > 0:
                if not tax_iva_exento:
                    raise UserError(
                        "No se encontró un impuesto de IVA Exento. "
                        "Debe crear un impuesto de compras con el grupo 'IVA Exento'."
                    )
                move_vals["line_ids"].append(line._create_line(line.exento, [tax_iva_exento.id]))

            if line.no_gravado > 0:
                if not tax_zero_id:
                    raise UserError(
                        "No se encontró un impuesto de IVA No Gravado. "
                        "Debe crear un impuesto de compras con el grupo 'IVA No Gravado'."
                    )

                move_vals["line_ids"].append(line._create_line(line.no_gravado, [tax_zero_id.id]))

            move = self.env["account.move"].create(move_vals)

            # Agregamos el rate despues de crear la factura, para que Odoo no lo recalcule
            if line.currency_rate and line.currency_rate != 1:
                wizard = self.env["account.move.change.rate"].create(
                    {
                        "move_id": move.id,
                        "currency_rate": line.currency_rate,
                    }
                )
                wizard.confirm()

            # Si tiene otros tributos, modificamos el valor por defecto con el wizard
            if line.otros_tributos > 0:
                invoice_taxes = (
                    self.env["account.invoice.tax"]
                    .with_context(active_model="account.move", active_ids=[move.id])
                    .create(
                        {
                            "move_id": move.id,
                        }
                    )
                )
                # Filtrar tax_line_ids para obtener solo el que corresponde a tax_otros_tributos
                otros_tributos_tax_line = invoice_taxes.tax_line_ids.filtered(
                    lambda l: l.tax_id.id == tax_otros_tributos.id
                )
                otros_tributos_tax_line.amount = line.otros_tributos

                invoice_taxes.action_update_tax()

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
            "views": [
                [self.env.ref("l10n_ar_import_bill.view_account_move_list_bill_import").id, "list"],
                [False, "form"],
            ],
        }
