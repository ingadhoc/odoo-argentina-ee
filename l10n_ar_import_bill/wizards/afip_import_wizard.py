import math

from odoo import api, fields, models
from odoo.exceptions import UserError


class AfipImportWizard(models.TransientModel):
    _name = "afip.import.wizard"
    _description = "Import AFIP bills from xlsx"
    _check_company_auto = True
    _check_company_domain = models.check_companies_domain_parent_of

    line_ids = fields.One2many("afip.import.wizard.line", "wizard_id", string="Líneas de Facturas")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    journal_id = fields.Many2one("account.journal", required=True, check_company=True, domain="journal_domain")
    auto_validate = fields.Boolean(string="Autovalidar Facturas Importadas", default=False)
    counterpart_account_id = fields.Many2one(
        "account.account",
        default=lambda self: self.env.company.get_unaffected_earnings_account(),
        string="Counterpart Account",
        help="Account used as counterpart when importing from settings",
        check_company=True,
    )
    total_bills_to_create = fields.Integer(
        compute="_compute_bills_to_create",
        string="Total de Facturas a Crear",
    )
    total_bills_exists = fields.Integer(
        compute="_compute_bills_exists",
        string="Total de Facturas Existentes",
    )

    #####
    # for initial import from settings
    #####

    file_data = fields.Binary(string="Archivo ARCA Excel", help="Archivo Excel exportado desde ARCA")
    file_name = fields.Char(string="Nombre del Archivo")
    journal_domain = fields.Binary(
        compute="_compute_journal_domain",
    )

    @api.depends_context("import_type")
    def _compute_journal_domain(self):
        if self._context.get("import_type") == "sale":
            domain = [("type", "in", "sale"), ("l10n_ar_is_pos", "=", False)]
        elif self._context.get("import_type") == "purchase":
            domain = [("type", "in", "purchase"), ("l10n_latam_use_documents", "=", True)]
        else:
            domain = []
        self.journal_domain = domain

    def action_process_file(self):
        """Process the uploaded file and open the main import wizard"""
        if not self.file_data:
            raise UserError("Please upload an Excel file to import.")

        # Create a temporary attachment
        attachment = self.env["ir.attachment"].create(
            {
                "name": self.file_name or "import.xlsx",
                "datas": self.file_data,
            }
        )
        return self.journal_id.with_context(
            initial_setup=True, default_counterpart_account_id=self.counterpart_account_id.id
        ).import_bills_from_xls(attachment)

    #####
    # common code for both import from settings and from journal
    #####

    def _compute_bills_to_create(self):
        self.total_bills_to_create = len(self.line_ids.filtered(lambda l: not l.exists))

    def _compute_bills_exists(self):
        self.total_bills_exists = len(self.line_ids.filtered(lambda l: l.exists))

    def action_confirm(self):  # noqa: C901
        # Validate if importing from settings (sales from ARCA)
        counterpart_account_id = None
        if self.env.context.get("initial_setup"):
            if not self.counterpart_account_id:
                raise UserError(
                    "Counterpart account is required when importing sales from ARCA. Please select an account."
                )

            # Check for invoices after accounting start date
            if self.company_id.account_opening_date:
                for line in self.line_ids.filtered(lambda l: not l.exists):
                    if line.date_invoice and line.date_invoice >= self.company_id.account_opening_date:
                        raise UserError(
                            f"Cannot import invoice dated {line.date_invoice.strftime('%Y-%m-%d')} "
                            f"because it is after the accounting start date "
                            f"({self.company_id.account_opening_date.strftime('%Y-%m-%d')}). "
                            "Only invoices before the accounting start date can be imported."
                        )

            counterpart_account_id = self.counterpart_account_id.id

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
        # Determine tax use type based on journal type
        tax_use_type = "sale" if self.journal_id.type == "sale" else "purchase"
        base_domain = [
            ("price_include", "=", False),
            ("company_id", "=", self.company_id.id),
            ("type_tax_use", "=", tax_use_type),
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
                "partner_id": partner.id,
                "ref": f"{document_type.name} {line.invoice_number}",
                "currency_id": currency.id,
                "journal_id": self.journal_id.id,
                "company_id": self.company_id.id,
                "line_ids": [],
                "l10n_latam_document_type_id": document_type.id,
                "invoice_date": line.date_invoice,
                "l10n_latam_document_number": line.invoice_number,
                "l10n_ar_afip_auth_code": line.cae,
                "l10n_ar_afip_auth_mode": "CAE",
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
                # Si no encuentra IVA ni importe "No Gravado" agrega la linea como "IVA No Corresponde"
                base_amount = line.amount_total
                if line.otros_tributos > 0:
                    base_amount -= line.otros_tributos

                if not tax_iva_no_corresponde:
                    raise UserError(
                        "No se encontró un impuesto de IVA No Corresponde. "
                        "Debe crear un impuesto de compras con el grupo 'IVA No Corresponde'"
                    )
                move_vals["line_ids"].append(line._create_line(base_amount, [tax_iva_no_corresponde.id]))

            move = self.env["account.move"].create(move_vals)

            # Agregamos el rate despues de crear la factura, para que Odoo no lo recalcule
            if line.currency_rate and line.currency_rate != 1:
                move.inverse_invoice_currency_rate = line.currency_rate

            # Si tiene otros tributos, modificamos el valor por defecto con el wizard
            if line.otros_tributos > 0:
                if not tax_otros_tributos:
                    raise UserError(
                        "No se encontró un impuesto de Otros Tributos. "
                        "Debe crear un impuesto de compras con el grupo de tributo 'Otros Tributos'."
                    )

                # Crear el wizard con el contexto correcto
                invoice_taxes = (
                    self.env["account.invoice.tax"]
                    .with_context(active_model="account.move", active_ids=[move.id])
                    .create({"move_id": move.id})
                )

                # Agregar la nueva línea de impuesto al wizard
                invoice_taxes.write(
                    {
                        "tax_line_ids": [
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
                    }
                )

                # Actualizar los impuestos en el movimiento
                invoice_taxes.action_update_tax()

            # If importing from settings, all lines (except receivable/payable) should use counterpart account
            if counterpart_account_id:
                # Odoo genera las líneas de impuestos automáticamente en el create() usando las cuentas por defecto
                # de los impuestos. Para forzar la cuenta de contrapartida sin que el motor de sincronización de Odoo
                # las sobreescriba, usamos 'skip_invoice_sync' en el contexto.
                move.line_ids.filtered(lambda x: x.display_type != "payment_term" and x.account_id).with_context(
                    skip_invoice_sync=True
                ).write({"account_id": counterpart_account_id})

            # Confirm the invoice only if auto_validate is True and the total matches line.amount_total
            if self.auto_validate and abs(move.amount_total - line.amount_total) <= 0.10 and line.amount_total > 0:
                move.action_post()

            new_moves += move

        # Determine title based on journal type
        title = (
            "Facturas de Cliente Importadas" if self.journal_id.type == "sale" else "Facturas de Proveedor Importadas"
        )

        return new_moves._get_records_action(
            name=title,
            target="current",
        )
