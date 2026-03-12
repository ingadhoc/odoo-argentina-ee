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
                "currency_id": currency.id,
                "journal_id": self.journal_id.id,
                "company_id": self.company_id.id,
                "l10n_ar_afip_auth_code": line.cae,
                "l10n_ar_afip_auth_mode": "CAE",
                "line_ids": [],
            }

            # Agregamos la linea con IVA y otros tributos (si existen).
            vat_rates = [
                (0.0, line.iva_0, line.neto_grav_iva_0),
                (2.5, line.iva_2_5, line.neto_grav_iva_2_5),
                (5.0, line.iva_5, line.neto_grav_iva_5),
                (10.5, line.iva_10_5, line.neto_grav_iva_10_5),
                (21.0, line.iva_21, line.neto_grav_iva_21),
                (27.0, line.iva_27, line.neto_grav_iva_27),
            ]

            for vat_rate, vat_amount, neto_amount in vat_rates:
                if not math.isnan(neto_amount) and neto_amount > 0:
                    # Search for the specific VAT tax
                    if vat_rate == 0.0:
                        # For 0% VAT, search for tax with AFIP code 3 and amount 0
                        iva_tax = self.env["account.tax"].search(
                            base_domain + [("amount", "=", 0.0), ("tax_group_id.l10n_ar_vat_afip_code", "=", "3")],
                            limit=1,
                        )
                    else:
                        iva_tax = self.env["account.tax"].search(
                            base_domain
                            + [
                                ("amount", "=", vat_rate),
                                ("tax_group_id.l10n_ar_vat_afip_code", "!=", False),
                            ],
                            limit=1,
                        )

                    if iva_tax:
                        if math.isnan(neto_amount) or neto_amount == 0:
                            neto_amount = round(vat_amount / (vat_rate / 100), 2)

                        move_vals["line_ids"].append(line._create_line(neto_amount, [iva_tax.id]))
                    else:
                        raise UserError(
                            f"No se encontró un impuesto de IVA para la alícuota {vat_rate}%. "
                            "Revise si este impuesto esta deshabilitado."
                        )

            # Add line for "exento" if it has a value
            if not math.isnan(line.exento) and line.exento > 0:
                if not tax_iva_exento:
                    raise UserError(
                        "No se encontró un impuesto de IVA Exento. "
                        "Debe crear un impuesto de compras con el grupo 'IVA Exento'."
                    )
                move_vals["line_ids"].append(line._create_line(line.exento, [tax_iva_exento.id]))

            # Add line for "no gravado" if it has a value
            if not math.isnan(line.no_gravado) and line.no_gravado > 0:
                if not tax_iva_no_gravado:
                    raise UserError(
                        "No se encontró un impuesto de IVA No Gravado. "
                        "Debe crear un impuesto de compras con el grupo 'IVA No Gravado'."
                    )
                move_vals["line_ids"].append(line._create_line(line.no_gravado, [tax_iva_no_gravado.id]))

            # Handle case when no VAT lines were created
            if not move_vals["line_ids"]:
                # Si no encuentra IVA ni importe "No Gravado" agrega la linea como "IVA No Corresponde" o "IVA No Gravado"
                base_amount = line.amount_total
                if line.otros_tributos > 0:
                    base_amount -= line.otros_tributos

                move_vals["line_ids"].append(line._create_line(base_amount, [tax_iva_no_corresponde.id]))

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
                tax_line = [
                    (
                        0,
                        0,
                        {
                            "tax_id": tax_otros_tributos.id,
                            "amount": line.otros_tributos,
                            "new_tax": True,
                        },
                    )
                ]

                # Crear el wizard sin modificar los impuestos existentes
                invoice_taxes = (
                    self.env["account.invoice.tax"]
                    .with_context(active_model="account.move", active_ids=[move.id])
                    .create({"move_id": move.id})
                )

                # Agregar la nueva línea de impuesto al wizard
                invoice_taxes.write({"tax_line_ids": tax_line})

                # Actualizar los impuestos en el movimiento
                invoice_taxes.action_update_tax()

            # Confirm the invoice only if the total matches line.amount_total
            if abs(move.amount_total - line.amount_total) <= 0.10 and line.amount_total > 0:
                move.action_post()

            new_moves += move

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
