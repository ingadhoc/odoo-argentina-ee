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
            and journal.company_id.l10n_ar_afip_responsibility_type_id.code == "1"
        ):
            attachments = self.env["ir.attachment"].browse(attachment_ids or [])

            if not attachments:
                raise UserError(_("No attachment was provided"))
            return journal.import_bills_from_xls(attachments)
        return super().create_document_from_attachment(attachment_ids)

    def import_bills_from_xls(self, attachments):
        for attachment in attachments:
            file_content = base64.b64decode(attachment.datas)
            try:
                df = pd.read_excel(BytesIO(file_content), engine="openpyxl")  # use openpyxl for .xlsx
            except Exception as e:
                raise UserError(
                    _(
                        "Error al leer el archivo. Por favor verifique que sea un archivo válido de tipo .xlsx. Error: %s"
                    )
                    % e
                )
            # El archivo tiene un header en la primera fila, lo eliminamos
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)

            # Definir el mapeo de columnas del archivo Excel a campos del modelo
            column_mapping = {
                "Fecha": "date_invoice",
                "Nro. Doc. Emisor": "partner_vat",
                "Tipo Doc. Emisor": "partner_identification_type",
                "Denominación Emisor": "partner_name",
                "Moneda": "currency",
                "Tipo Cambio": "currency_rate",
                "Imp. Total": "amount_total",
                "Tipo": "document_type",
                "Neto No Gravado": "no_gravado",
                "Op. Exentas": "exento",
                "Otros Tributos": "otros_tributos",
                "Cód. Autorización": "cae",
                "Neto Grav. IVA 0%": "neto_grav_iva_0",
                "IVA 2,5%": "iva_2_5",
                "Neto Grav. IVA 2,5%": "neto_grav_iva_2_5",
                "IVA 5%": "iva_5",
                "Neto Grav. IVA 5%": "neto_grav_iva_5",
                "IVA 10,5%": "iva_10_5",
                "Neto Grav. IVA 10,5%": "neto_grav_iva_10_5",
                "IVA 21%": "iva_21",
                "Neto Grav. IVA 21%": "neto_grav_iva_21",
                "IVA 27%": "iva_27",
                "Neto Grav. IVA 27%": "neto_grav_iva_27",
            }

            # Columnas adicionales requeridas para procesamiento
            additional_required_columns = ["Punto de Venta", "Número Desde"]

            # Validar que todas las columnas requeridas estén presentes
            required_columns = list(column_mapping.keys()) + additional_required_columns
            self._validate_required_columns(df, required_columns)

            # Optimización: Convertir todas las fechas de una vez usando vectorización de pandas
            df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True).dt.date

            # Optimización: Convertir VAT a string de una vez
            df["Nro. Doc. Emisor"] = df["Nro. Doc. Emisor"].astype(int).astype(str)

            # Optimización: Generar número de factura usando vectorización
            df["Punto de Venta"] = df["Punto de Venta"].astype(int)
            df["Número Desde"] = df["Número Desde"].astype(int)
            df["invoice_number"] = (
                df["Punto de Venta"].astype(str).str.zfill(5) + "-" + df["Número Desde"].astype(str).str.zfill(8)
            )

            # Optimización: Convertir columnas numéricas de una vez
            numeric_columns = [
                "Imp. Total",
                "Tipo Cambio",
                "Neto No Gravado",
                "Op. Exentas",
                "Otros Tributos",
                "Neto Grav. IVA 0%",
                "IVA 2,5%",
                "Neto Grav. IVA 2,5%",
                "IVA 5%",
                "Neto Grav. IVA 5%",
                "IVA 10,5%",
                "Neto Grav. IVA 10,5%",
                "IVA 21%",
                "Neto Grav. IVA 21%",
                "IVA 27%",
                "Neto Grav. IVA 27%",
            ]

            existing_numeric_cols = [col for col in numeric_columns if col in df.columns]
            for col in existing_numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

            # Optimización: Renombrar columnas directamente en el DataFrame
            df = df.rename(columns=column_mapping)

            # Optimización: Convertir directamente a lista de tuplas solo con campos válidos
            valid_fields = [
                "invoice_number",
            ] + list(column_mapping.values())

            # Validar que todas las columnas necesarias estén presentes después del renombrado
            self._validate_required_columns(df, valid_fields)

            # Filtrar solo las columnas que existen en el modelo
            filtered_df = df[valid_fields]
            line_vals = [(0, 0, row) for row in filtered_df.to_dict(orient="records")]

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

    def _validate_required_columns(self, df, required_columns):
        """Valida que el DataFrame contenga todas las columnas requeridas.

        Args:
            df: DataFrame de pandas
            required_columns: Lista de nombres de columnas requeridas

        Raises:
            UserError: Si falta alguna columna requerida
        """
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise UserError(
                _(
                    "El archivo no contiene las siguientes columnas requeridas: %s.\n\n"
                    "Si no realizó cambios manuales en el archivo Excel, es posible que ARCA haya "
                    "modificado el formato del archivo. En ese caso, por favor reporte el inconveniente "
                    "a través de un ticket de soporte."
                )
                % ", ".join(missing_columns)
            )
