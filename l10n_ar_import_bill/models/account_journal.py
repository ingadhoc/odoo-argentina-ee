# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from io import BytesIO

import pandas as pd
from odoo import _, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def create_document_from_attachment(self, attachment_ids=None):
        # OVERRIDE
        journal = self or self.browse(self.env.context.get("default_journal_id"))

        if (
            journal.type == "purchase"
            and journal.company_id.country_code == "AR"
            and journal.company_id.chart_template == "ar_ri"
        ):
            attachments = self.env["ir.attachment"].browse(attachment_ids or [])

            if not attachments:
                raise UserError(_("No attachment was provided"))
            return journal.import_bills_from_xls(attachments)
        return super().create_document_from_attachment(attachment_ids)

    def import_bills_from_xls(self, attachments):
        for attachment in attachments:
            file_content = base64.b64decode(attachment.datas)
            df = pd.read_excel(BytesIO(file_content), engine="openpyxl")  # use openpyxl for .xlsx

            # El archivo tiene un header en la primera fila, lo eliminamos
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)

            data_list = df.to_dict(orient="records")

            line_vals = []

            for row in data_list:
                invoice_number = row["Número"]
                date_invoice = pd.to_datetime(row["Fecha"], dayfirst=True).date()
                partner_vat = str(int(row["Nro. Doc. Emisor"]))
                partner_identification_type = row["Tipo Doc. Emisor"]
                partner_name = row["Denominación Emisor"]
                currency = row["Moneda"]
                currency_rate = row["Tipo Cambio"]
                amount_total = float(row["Imp. Total"])
                document_type = row["Tipo"]
                valor_no_gravado = row["Neto No Gravado"]
                valor_exento = row["Op. Exentas"]
                otros_tributos = row["Otros Tributos"]
                cae = row["Cód. Autorización"]
                neto_grav_iva_0 = row["Neto Grav. IVA 0%"]
                iva_2_5 = row["IVA 2,5%"]
                neto_grav_iva_2_5 = row["Neto Grav. IVA 2,5%"]
                iva_5 = row["IVA 5%"]
                neto_grav_iva_5 = row["Neto Grav. IVA 5%"]
                iva_10_5 = row["IVA 10,5%"]
                neto_grav_iva_10_5 = row["Neto Grav. IVA 10,5%"]
                iva_21 = row["IVA 21%"]
                neto_grav_iva_21 = row["Neto Grav. IVA 21%"]
                iva_27 = row["IVA 27%"]
                neto_grav_iva_27 = row["Neto Grav. IVA 27%"]

                dict_data = (
                    0,
                    0,
                    {
                        "invoice_number": invoice_number,
                        "date_invoice": date_invoice,
                        "partner_vat": partner_vat,
                        "partner_identification_type": partner_identification_type,
                        "partner_name": partner_name,
                        "currency": currency,
                        "currency_rate": currency_rate,
                        "amount_total": amount_total,
                        "document_type": document_type,
                        "no_gravado": valor_no_gravado,
                        "exento": valor_exento,
                        "otros_tributos": otros_tributos,
                        "neto_grav_iva_0": neto_grav_iva_0,
                        "iva_2_5": iva_2_5,
                        "neto_grav_iva_2_5": neto_grav_iva_2_5,
                        "iva_5": iva_5,
                        "neto_grav_iva_5": neto_grav_iva_5,
                        "iva_10_5": iva_10_5,
                        "neto_grav_iva_10_5": neto_grav_iva_10_5,
                        "iva_21": iva_21,
                        "neto_grav_iva_21": neto_grav_iva_21,
                        "iva_27": iva_27,
                        "neto_grav_iva_27": neto_grav_iva_27,
                        "cae": cae,
                    },
                )

                line_vals.append(dict_data)

            wizard = self.env["afip.import.wizard"].create(
                {
                    "journal_id": self.id,
                    "company_id": self.company_id.id,
                }
            )
            wizard.write({"line_ids": line_vals})

            return {
                "name": "Importación de Facturas de Proveedor",
                "type": "ir.actions.act_window",
                "res_model": "afip.import.wizard",
                "target": "new",
                "views": [[self.env.ref("l10n_ar_import_bill.view_afip_import_wizard_form").id, "form"]],
                "res_id": wizard.id,
            }
