# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io
import zipfile

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

ALIQUOT_CODES_LIST = [
    (0, "3"),
    (10.5, "4"),
    (21, "5"),
    (27, "6"),
    (5, "8"),
    (2.5, "9"),
]


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
        report_credito_data = self._generate_iva_credito_data(company, options, is_restitucion=False)
        report_credito_restitucion_data = self._generate_iva_credito_data(company, options, is_restitucion=True)
        report_debito_data = self._generate_iva_debito_data(company, options)
        report_debito_restitucion_data = self._generate_iva_debito_data(company, options, is_restitucion=True)

        # Create ZIP content
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Crear archivos de Débito fiscal
            content_debito = self._format_debit_report_content(report_debito_data)
            zf.writestr("IVA_Debito.csv", content_debito)
            content_restitucion_debito = self._format_debit_report_content(
                report_debito_restitucion_data, is_restitucion=True
            )
            zf.writestr("IVA_Restitucion_Debito.csv", content_restitucion_debito)
            # Crear archivos de Crédito fiscal
            content_credito = self._format_credit_report_content(report_credito_data)
            zf.writestr("IVA_Credito.csv", content_credito)
            content_restitucion_credito = self._format_credit_report_content(
                report_credito_restitucion_data, is_restitucion=True
            )
            zf.writestr("IVA_Restitucion_Credito.csv", content_restitucion_credito)

        file_content = stream.getvalue()
        return {
            "file_name": export_file_name,
            "file_content": file_content,
            "file_type": "zip",
        }

    def _get_domain_move(self, options, is_debit=False, is_restitucion=False):
        company = self.env.company
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

        if is_debit:
            move_type = "out_invoice" if not is_restitucion else "out_refund"
        else:
            move_type = "in_invoice" if not is_restitucion else "in_refund"
        return domain_base + [("move_type", "=", move_type), ("move_id.state", "=", "posted")]

    def _generate_iva_debito_data(self, company, options, is_restitucion=False):
        """Generate the IVA Débito y Restitución data"""

        # Get tag for "venta bienes de uso"
        tag_venta_bienes_de_uso = self.env.ref("l10n_ar_ux.tag_venta_bienes_de_uso")

        if not tag_venta_bienes_de_uso:
            # Fallback if tag doesn't exist
            tag_venta_bienes_de_uso = self.env["account.account.tag"]

        # Responsibility type codes
        codes_ri = ["1"]
        codes_monotributo = ["6", "13", "16"]

        # Activities: company activity + activities used in accounts
        if not company.l10n_ar_afip_activity_id:
            raise UserError("Debe establecer la actividad principal en la compañía para poder descargar el archivo.")

        activities = company.l10n_ar_afip_activity_id + self.env["account.account"].search(
            [("l10n_ar_afip_activity_id", "!=", False)]
        ).mapped("l10n_ar_afip_activity_id")

        lines_data = []
        move_type = "out_invoice" if not is_restitucion else "out_refund"
        domain_move = self._get_domain_move(options, is_debit=True, is_restitucion=is_restitucion)

        for activity in activities:
            if activity == company.l10n_ar_afip_activity_id:
                # Company main activity: include accounts with this activity or no activity set
                domain_activity = domain_move + [("account_id.l10n_ar_afip_activity_id", "in", [activity.id, False])]
            else:
                domain_activity = domain_move + [("account_id.l10n_ar_afip_activity_id", "=", activity.id)]

            if move_type == "out_invoice":
                # TIPOS en débito fiscal
                # 1. VENTA de cosas muebles, Obras, Locaciones y/o Prestaciones de Servicios
                # 2. Venta de Bienes de Uso
                tipos_de_operacion = ["1", "2", "3"]
            else:
                # refund - restitución débito fiscal
                # 1 - Venta de Cosas Muebles, Obras, Locaciones, Bienes de Uso y/o Prestaciones de Servicios
                tipos_de_operacion = ["1", "3"]

            for tipo_de_operacion in tipos_de_operacion:
                # Operation type discrimination (only for débito fiscal)
                if tipo_de_operacion == "3":
                    domain_final = domain_activity + [
                        ("tax_ids.tax_group_id.l10n_ar_vat_afip_code", "in", ["0", "1", "2"])
                    ]
                    lines = self.env["account.move.line"].search(domain_final)
                    if lines:
                        lines_data.append(
                            {
                                "activity_code": activity.code,
                                "tipo_operacion": "3",
                                "tipo_sujeto": "",
                                "aliquot_code": "",
                                "monto_neto_gravado": "",
                                "debito_fiscal_facturado": "",
                                "debito_fiscal_operacion_dacion_en_pago": "",
                                "monto_neto_exento_o_no_gravado": abs(sum(lines.mapped("balance"))),
                            }
                        )
                    break
                if move_type == "out_invoice":
                    if tipo_de_operacion == "1":
                        # Exclude "Bienes de Uso"
                        domain_op = domain_activity + [("account_id.tag_ids", "not in", [tag_venta_bienes_de_uso.id])]
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

                    for aliquot, aliquot_code in ALIQUOT_CODES_LIST:
                        domain_final = domain_subject + [
                            ("tax_ids.tax_group_id.l10n_ar_vat_afip_code", "=", aliquot_code)
                        ]
                        lines = self.env["account.move.line"].search(domain_final)
                        if not lines:
                            continue

                        monto_neto_gravado = sum(lines.mapped("balance"))
                        impuesto = float_round(monto_neto_gravado * aliquot / 100, precision_digits=2)

                        # TODO: diferenciar debito_fiscal_facturado de debito_fiscal_operacion_dacion_en_pago
                        lines_data.append(
                            {
                                "activity_code": activity.code,
                                "tipo_operacion": tipo_de_operacion,
                                "tipo_sujeto": tipo_de_sujeto,
                                "aliquot_code": aliquot_code,
                                "monto_neto_gravado": abs(monto_neto_gravado),
                                "debito_fiscal_facturado": abs(impuesto),
                                "debito_fiscal_operacion_dacion_en_pago": abs(impuesto),
                            }
                        )

        return lines_data

    @api.model
    def _format_debit_report_content(self, lines_data, is_restitucion=False):
        """Format the report data into a CSV file content"""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_NONNUMERIC)
        headers = [
            "Actividad",
            "Tipo de Operación",
            "Tipo de sujeto comprador",
            "Código de Alícuota",
            "Monto Neto Gravado",
            "Débito Fiscal Facturado" if not is_restitucion else "Debito Fiscal a Restituir",
            "Débito Fiscal Operación Dación en Pago" if not is_restitucion else "Monto Neto Exento o No Gravado",
            "Monto Neto Exento o No Gravado" if not is_restitucion else "",
        ]

        if lines_data:
            writer.writerow(headers)

            # Write data rows
            for line in lines_data:
                row = [
                    line["activity_code"],
                    line["tipo_operacion"],
                    line["tipo_sujeto"],
                    line["aliquot_code"],
                    f"{line['monto_neto_gravado']:.2f}".replace(".", ",")
                    if not line.get("monto_neto_exento_o_no_gravado")
                    else "",
                    f"{line['debito_fiscal_facturado']:.2f}".replace(".", ",")
                    if not line.get("monto_neto_exento_o_no_gravado")
                    else "",
                    f"{line['monto_neto_exento_o_no_gravado']:.2f}".replace(".", ",")
                    if line.get("monto_neto_exento_o_no_gravado")
                    else "",
                ]
                if not is_restitucion:
                    row.insert(
                        6,
                        f"{line['debito_fiscal_operacion_dacion_en_pago']:.2f}".replace(".", ",")
                        if not line.get("monto_neto_exento_o_no_gravado")
                        else "",
                    )
                writer.writerow(row)

        csv_content = output.getvalue()
        output.close()

        return csv_content.encode("utf-8")

    def _generate_iva_credito_data(self, company, options, is_restitucion=False):
        def _append_lines_data(domain, concepto=False, company_iva_default_tag=False):
            for aliquot, aliquot_code in ALIQUOT_CODES_LIST:
                domain_final = domain + [("tax_ids.tax_group_id.l10n_ar_vat_afip_code", "=", aliquot_code)]
                if not company_iva_default_tag:
                    domain_final.append(("account_id.tag_ids", "=", False))
                lines = self.env["account.move.line"].search(domain_final)
                if not lines:
                    continue

                monto_neto_gravado = sum(lines.mapped("balance"))
                credito_fiscal_facturado = float_round(monto_neto_gravado * aliquot / 100, precision_digits=2)

                # TODO: por ahora llevamos lo mismo a crédito fiscal facturado y crédito fiscal computable
                # pero deberíamos diferenciarlo, ver si tiene que ver con prorrateo de crédito fiscal
                lines_data.append(
                    {
                        "concepto": concepto if company_iva_default_tag else "",
                        "aliquot_code": aliquot_code,
                        "monto_neto_gravado": abs(monto_neto_gravado),
                        "credito_fiscal_facturado": abs(credito_fiscal_facturado),
                        "credito_fiscal_computable": abs(credito_fiscal_facturado),
                    }
                )

        # Conceptos en crédito fiscal
        # 1. Compra de Bienes (excepto Bienes de Uso)
        # 2. Locaciones
        # 3. Prestaciones de Servicios
        # 4. Inversiones de Bienes de Uso
        conceptos = {
            "1": self.env.ref("l10n_ar_ux.tag_compra_bienes").id,
            "2": self.env.ref("l10n_ar_ux.tag_locaciones").id,
            "3": self.env.ref("l10n_ar_ux.tag_prestaciones_de_ss").id,
            "4": self.env.ref("l10n_ar_ux.tag_compra_bienes_de_uso").id,
        }

        lines_data = []
        domain_move = self._get_domain_move(options, is_debit=False, is_restitucion=is_restitucion)
        # Si no hay tag en la compañía ni en las cuentas entonces dejamos campo concepto vacío
        if not company.l10n_ar_iva_simple_default_tag.id:
            _append_lines_data(domain=domain_move, concepto=False)

        # Acá si buscamos si hay tag en la cuenta/compañía
        for concepto, tag in conceptos.items():
            if tag == company.l10n_ar_iva_simple_default_tag.id:
                # si hay apuntes con cuenta sin etiquetas entonces asignamos el de la compañía
                domain_concepto = domain_move + [
                    "|",
                    ("account_id.tag_ids", "in", [tag]),
                    ("account_id.tag_ids", "=", False),
                ]
            else:
                domain_concepto = domain_move + [("account_id.tag_ids", "in", [tag])]

            _append_lines_data(domain=domain_concepto, concepto=concepto, company_iva_default_tag=True)
        return lines_data

    @api.model
    def _format_credit_report_content(self, lines_data, is_restitucion=False):
        """Format the report data into a CSV file content"""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_NONNUMERIC)
        headers = [
            "Concepto",
            "Código de Alícuota",
            "Monto Neto Gravado",
            "Crédito Fiscal Facturado",
        ]
        if not is_restitucion:
            headers.append("Crédito Fiscal Computable")
        writer.writerow(headers)
        # Write data rows
        for line in lines_data:
            row = [
                line["concepto"],
                line["aliquot_code"],
                f"{line['monto_neto_gravado']:.2f}".replace(".", ","),
                f"{line['credito_fiscal_facturado']:.2f}".replace(".", ","),
            ]
            if not is_restitucion:
                row.append(f"{line['credito_fiscal_computable']:.2f}".replace(".", ","))
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
