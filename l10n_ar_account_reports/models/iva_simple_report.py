# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io
import zipfile

from odoo import _, models
from odoo.tools.float_utils import float_round


class ReporteIvaSimpleCustomHandler(models.AbstractModel):
    _name = "l10n_ar.iva.simple.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Reporte IVA Simple Custom Handler"

    def _get_custom_display_config(self):
        parent_config = super()._get_custom_display_config()
        return parent_config

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button for ZIP file
        zip_export_button = {
            "name": _("Reporte IVA Simple"),
            "sequence": 30,
            "action": "export_file",
            "action_param": "iva_simple_export_to_zip",
            "file_export_type": _("ZIP"),
        }

        options["buttons"].append(zip_export_button)

    def iva_simple_export_to_zip(self, options):
        """Export method that generates IVA Simple report"""
        company = self.env.company

        # Build file name
        export_file_name = f"IVA_Simple_{options['date']['date_to']}"

        # Generate report data
        report_credito_data = self._generate_iva_credito_restitucion_data(company, options)
        report_debito_data = self._generate_iva_debito_restitucion_data(company, options)

        # Create ZIP content
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Add the main report file as CSV
            content_debito = self._format_report_content(report_debito_data)
            zf.writestr("IVA_Debito_y_Restitucion_Debito.csv", content_debito)
            content_credito = self._format_report_content(report_credito_data)
            zf.writestr("IVA_Credito_y_Restitucion_Credito.csv", content_credito)

        file_content = stream.getvalue()
        return {
            "file_name": export_file_name,
            "file_content": file_content,
            "file_type": "zip",
        }

    def _generate_iva_debito_restitucion_data(self, company, options):
        """Generate the IVA Débito y Restitución data"""

        # Get tag for "venta bienes de uso"
        tag_venta_bienes_de_uso = self.env.ref("l10n_ar_ux.tag_venta_bienes_de_uso", raise_if_not_found=False)
        if not tag_venta_bienes_de_uso:
            # Fallback if tag doesn't exist
            tag_venta_bienes_de_uso = self.env["account.account.tag"]

        # Responsibility type codes
        codes_ri = ["1"]
        codes_monotributo = ["6", "13", "16"]

        # Activities: company activity + activities used in accounts
        activities = company.l10n_ar_afip_activity_id + self.env["account.account"].search(
            [("l10n_ar_afip_activity_id", "!=", False)]
        ).mapped("l10n_ar_afip_activity_id")

        # Aliquot codes mapping
        aliquot_codes_list = [
            (0, ["0", "1", "2", "3"]),
            (10.5, ["4"]),
            (21, ["5"]),
            (27, ["6"]),
            (5, ["8"]),
            (2.5, ["9"]),
        ]

        # Base domain for account move lines
        domain_base = [
            ("company_id", "=", company.id),
            ("display_type", "=", "product"),
        ]

        # Add date filters
        if options.get("date", {}).get("date_from"):
            domain_base.append(("date", ">=", options["date"]["date_from"]))
        if options.get("date", {}).get("date_to"):
            domain_base.append(("date", "<=", options["date"]["date_to"]))

        lines_data = []

        for move_type in ["out_invoice", "out_refund"]:
            domain_move = domain_base + [("move_type", "=", move_type)]

            for activity in activities:
                if activity == company.l10n_ar_afip_activity_id:
                    # Company main activity: include accounts with this activity or no activity set
                    domain_activity = domain_move + [
                        ("account_id.l10n_ar_afip_activity_id", "in", [activity.id, False])
                    ]
                else:
                    domain_activity = domain_move + [("account_id.l10n_ar_afip_activity_id", "=", activity.id)]

                if move_type == "out_invoice":
                    # TIPOS en débito fiscal
                    # 1. VENTA de cosas muebles, Obras, Locaciones y/o Prestaciones de Servicios
                    # 2. Venta de Bienes de Uso
                    tipos_de_operacion = ["1", "2"]
                else:
                    # refund - restitución débito fiscal
                    # 1 - Venta de Cosas Muebles, Obras, Locaciones, Bienes de Uso y/o Prestaciones de Servicios
                    tipos_de_operacion = ["1"]

                for tipo_de_operacion in tipos_de_operacion:
                    # Operation type discrimination (only for débito fiscal)
                    if move_type == "out_invoice":
                        if tipo_de_operacion == "1":
                            # Exclude "Bienes de Uso"
                            domain_op = domain_activity + [
                                ("account_id.tag_ids", "not in", [tag_venta_bienes_de_uso.id])
                            ]
                        else:
                            # Only "Bienes de Uso"
                            domain_op = domain_activity + [("account_id.tag_ids", "in", [tag_venta_bienes_de_uso.id])]
                    else:
                        domain_op = list(domain_activity)

                    tipos_de_sujetos = ["1", "2", "3"]
                    # tipos_de_sujetos:
                    # 1- Operaciones con Responsables Inscriptos
                    # 2 - Operaciones con Monotributistas
                    # 3 - Operaciones con Consumidores Finales, Exentos y No Alcanzados

                    for tipo_de_sujeto in tipos_de_sujetos:
                        if tipo_de_sujeto == "1":
                            domain_subject = domain_op + [
                                ("partner_id.l10n_ar_afip_responsibility_type_id.code", "in", codes_ri)
                            ]
                        elif tipo_de_sujeto == "2":
                            domain_subject = domain_op + [
                                ("partner_id.l10n_ar_afip_responsibility_type_id.code", "in", codes_monotributo)
                            ]
                        elif tipo_de_sujeto == "3":
                            domain_subject = domain_op + [
                                (
                                    "partner_id.l10n_ar_afip_responsibility_type_id.code",
                                    "not in",
                                    codes_ri + codes_monotributo,
                                )
                            ]
                        else:
                            domain_subject = list(domain_op)

                        for aliquot, aliquot_codes in aliquot_codes_list:
                            domain_final = domain_subject + [
                                ("tax_ids.tax_group_id.l10n_ar_vat_afip_code", "in", aliquot_codes)
                            ]

                            lines = self.env["account.move.line"].search(domain_final)
                            if not lines:
                                continue

                            monto_neto_gravado = sum(lines.mapped("balance"))
                            impuesto = float_round(monto_neto_gravado * aliquot / 100, precision_digits=2)

                            lines_data.append(
                                {
                                    "activity_code": activity.code,
                                    "tipo_operacion": tipo_de_operacion,
                                    "tipo_sujeto": tipo_de_sujeto,
                                    "aliquot_codes": aliquot_codes,
                                    "aliquot_rate": aliquot,
                                    "monto_neto_gravado": monto_neto_gravado,
                                    "impuesto": impuesto,
                                    "move_type": move_type,
                                }
                            )

        return lines_data

    def _generate_iva_credito_restitucion_data(self, company, options):
        # Get tag for "venta bienes de uso"
        tag_compra_bienes_de_uso = self.env.ref("l10n_ar_ux.tag_compra_bienes_de_uso", raise_if_not_found=False)
        if not tag_compra_bienes_de_uso:
            # Fallback if tag doesn't exist
            tag_compra_bienes_de_uso = self.env["account.account.tag"]

        # Activities: company activity + activities used in accounts
        activities = company.l10n_ar_afip_activity_id + self.env["account.account"].search(
            [("l10n_ar_afip_activity_id", "!=", False)]
        ).mapped("l10n_ar_afip_activity_id")

        # Aliquot codes mapping
        aliquot_codes_list = [
            (0, ["0", "1", "2", "3"]),
            (10.5, ["4"]),
            (21, ["5"]),
            (27, ["6"]),
            (5, ["8"]),
            (2.5, ["9"]),
        ]
        # Base domain for account move lines
        domain_base = [
            ("company_id", "=", company.id),
            ("display_type", "=", "product"),
        ]

        # Add date filters
        if options.get("date", {}).get("date_from"):
            domain_base.append(("date", ">=", options["date"]["date_from"]))
        if options.get("date", {}).get("date_to"):
            domain_base.append(("date", "<=", options["date"]["date_to"]))

        lines_data = []

        for move_type in ["in_invoice", "in_refund"]:
            domain_move = domain_base + [("move_type", "=", move_type)]

            for activity in activities:
                if activity == company.l10n_ar_afip_activity_id:
                    # Company main activity: include accounts with this activity or no activity set
                    domain_activity = domain_move + [
                        ("account_id.l10n_ar_afip_activity_id", "in", [activity.id, False])
                    ]
                else:
                    domain_activity = domain_move + [("account_id.l10n_ar_afip_activity_id", "=", activity.id)]

                if move_type == "in_invoice":
                    # TIPOS en crédito fiscal
                    # 1. Compra de Bienes (excepto Bienes de Uso)
                    # 2. Locaciones
                    # 3. Prestaciones de Servicios
                    tipos_de_operacion = ["1", "2", "3"]
                else:
                    # Refund - restitución crédito fiscal
                    # 4. Inversiones de Bienes de Uso
                    tipos_de_operacion = ["4"]

                for tipo_de_operacion in tipos_de_operacion:
                    # Operation type discrimination (only for crédito fiscal)
                    if move_type == "in_invoice":
                        if tipo_de_operacion in ["1", "2", "3"]:
                            # Exclude "Bienes de Uso"
                            domain_op = domain_activity + [
                                ("account_id.tag_ids", "not in", [tag_compra_bienes_de_uso.id])
                            ]
                        else:
                            # Only "Bienes de Uso"
                            domain_op = domain_activity + [("account_id.tag_ids", "in", [tag_compra_bienes_de_uso.id])]
                    else:
                        domain_op = list(domain_activity)

                        for aliquot, aliquot_codes in aliquot_codes_list:
                            domain_final = domain_op + [
                                ("tax_ids.tax_group_id.l10n_ar_vat_afip_code", "in", aliquot_codes)
                            ]

                            lines = self.env["account.move.line"].search(domain_final)
                            if not lines:
                                continue

                            monto_neto_gravado = sum(lines.mapped("balance"))
                            impuesto = float_round(monto_neto_gravado * aliquot / 100, precision_digits=2)

                            lines_data.append(
                                {
                                    "activity_code": activity.code,
                                    "tipo_operacion": tipo_de_operacion,
                                    "aliquot_codes": aliquot_codes,
                                    "aliquot_rate": aliquot,
                                    "monto_neto_gravado": monto_neto_gravado,
                                    "impuesto": impuesto,
                                    "move_type": move_type,
                                }
                            )

    def _format_report_content(self, lines_data):
        """Format the report data into a CSV file content"""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_NONNUMERIC)

        # CSV Headers
        headers = [
            "Código Actividad",
            "Tipo Operación",
            "Códigos Alícuota",
            "Alícuota (%)",
            "Monto Neto Gravado",
            "Impuesto",
        ]

        if lines_data:
            if lines_data[0].get("tipo_sujeto"):
                headers.insert(2, "Tipo Sujeto")
            writer.writerow(headers)

            # Write data rows
            for line in lines_data:
                row = [
                    line["activity_code"],
                    line["tipo_operacion"],
                    ",".join(line["aliquot_codes"]),
                    f"{line['aliquot_rate']:.1f}",
                    f"{line['monto_neto_gravado']:.2f}".replace(".", ","),
                    f"{line['impuesto']:.2f}".replace(".", ","),
                ]
                if lines_data[0].get("move_type"):
                    row.insert(2, line["tipo_sujeto"])
                writer.writerow(row)

        csv_content = output.getvalue()
        output.close()

        return csv_content.encode("utf-8")

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        """Generate dynamic lines for the report view"""
        lines = []

        # Por ahora devolvemos lineas sin contenido
        line = {
            "id": report._get_generic_line_id(None, None, markup="placeholder"),
            "name": _("Reporte IVA Simple"),
            "level": 1,
            "columns": [{"name": ""} for _ in options["columns"]],
        }
        lines.append((0, line))

        return lines
