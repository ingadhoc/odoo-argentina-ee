# Part of Odoo. See LICENSE file for full copyright and licensing details.

from io import BytesIO
import pandas as pd
from odoo import _, fields, models
from odoo.exceptions import UserError
import base64


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def create_document_from_attachment(self, attachment_ids=None):
        # OVERRIDE
        journal = self or self.browse(self.env.context.get('default_journal_id'))

        if journal.type == 'purchase' and journal.company_id.country_code == 'AR':
            attachments = self.env['ir.attachment'].browse(attachment_ids or [])

            if not attachments:
                raise UserError(_("No attachment was provided"))
            return journal.import_bills_from_xls(attachments)
        return super().create_document_from_attachment(attachment_ids)

    def import_bills_from_xls(self, attachments):

        # company = self.company_id

        for attachment in attachments:
            # if 'xlsx' in attachment.datas_fname:
            file_content = base64.b64decode(attachment.datas)
            df = pd.read_excel(BytesIO(file_content), engine='openpyxl')  # use openpyxl for .xlsx

            # El archivo tiene un header en la primera fila, lo eliminamos
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)

            data_list = df.to_dict(orient='records')

            pre_data = []

            for row in data_list:
                sequence_number = int(row['Número Desde'])
                sequence_prefix = int(row['Punto de Venta'])
                invoice_number = f"{sequence_prefix:05d}-{sequence_number:08d}"
                date_invoice = pd.to_datetime(row["Fecha"], dayfirst=True).date()
                partner_vat = str(int(row["Nro. Doc. Vendedor"]))
                partner_name = row["Denominación Vendedor"]
                currency = row["Moneda"]
                amount_total = float(row["Total"])
                document_type_id = self.get_invoice_type(row["Tipo"]).id

                dict_data = {
                    "invoice_number": invoice_number,
                    "date_invoice": date_invoice,
                    "partner_vat": partner_vat,
                    "partner_name": partner_name,
                    "currency": currency,
                    "amount_total": amount_total,
                    "document_type_id": document_type_id,
                    "raw_data": row,  # guardamos todo por si hace falta mostrarlo
                }

                pre_data.append(dict_data)

            wizard = self.env["afip.import.wizard"].create({
                "journal_id": self.id,
                "company_id": self.company_id.id,
            })
            line_vals = []
            for data in pre_data:
                line_vals.append((0, 0, {
                    "invoice_number": data["invoice_number"],
                    "partner_name": data["partner_name"],
                    "partner_vat": data["partner_vat"],
                    "date_invoice": data["date_invoice"],
                    "currency": data["currency"],
                    "amount_total": data["amount_total"],
                    "document_type_id": data["document_type_id"],
                }))
            wizard.write({"line_ids": line_vals})

            return {
                "name": "Importación de Facturas de Proveedor",
                "type": "ir.actions.act_window",
                "res_model": "afip.import.wizard",
                "target": "new",
                "views": [[self.env.ref("l10n_ar_import_bill.view_afip_import_wizard_form").id, "form"]],
                "res_id": wizard.id,
            }

    def get_invoice_type(self, invoice_type):

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
