# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io
import zipfile
from csv import DictWriter

from odoo import _, api, models
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools import SQL


class L10n_ArTaxReportHandler(models.AbstractModel):
    _inherit = "l10n_ar.tax.report.handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        options["buttons"] += [
            {
                "name": _("VAT Simple Report (ZIP)"),
                "sequence": 31,
                "action": "export_file",
                "action_param": "vat_simple_export_files_to_zip",
                "file_export_type": _("ZIP"),
            },
        ]

    ####################################################
    # EXPORT/PRINT
    ####################################################

    def vat_simple_export_files_to_zip(self, options):
        """Export method that lets us export the IVA Simple Report to a zip archive.
        It contains the files that we upload to ARCA for vat uploads.
        Specification: https://www.afip.gob.ar/iva/responsables-inscriptos/ayuda/manuales.asp"""
        tax_types = self._vat_book_get_selected_tax_types(options)

        missing_fallback_activity = "sale" in tax_types and not self.env.company.l10n_ar_afip_activity_id
        if missing_fallback_activity and not options.get("l10n_ar_simple_ignore_errors"):
            report = self.env["account.report"].browse(options["report_id"])
            error_msg = _(
                "Warning, activities are not set as a fallback on the company. As such the Sales VAT Simple files may be incorrect. Please set a fallback activity on the company or ignore this warning to generate the file anyway."
            )
            action_vals = report.export_file(
                {**options, "l10n_ar_simple_ignore_errors": True}, "vat_simple_export_files_to_zip"
            )
            raise RedirectWarning(error_msg, action_vals, _("Generate VAT Simple Report"))

        file_types = [f"{tax}_{suffix}" for tax in tax_types for suffix in ["invoice", "refund"]]
        file_names = {
            "sale_invoice": "DEBITO",
            "sale_refund": "REST_DEBITO",
            "purchase_invoice": "CREDITO",
            "purchase_refund": "REST_CREDITO",
        }

        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_type in file_types:
                move_ids = self._vat_simple_get_csv_move_ids(options, file_type)
                if not move_ids:
                    continue
                file_data = self._vat_simple_get_data(file_type, move_ids)
                if file_data:
                    file_name = f"{file_names[file_type]}_{options['date']['date_to']}.csv"
                    zf.writestr(file_name, file_data)
        file_content = stream.getvalue()
        return {
            "file_name": f"IVA_simple_{options['date']['date_to']}",
            "file_content": file_content,
            "file_type": "zip",
        }

    ####################################################
    # VAT SIMPLE HELPERS
    ####################################################
    @api.model
    def _vat_simple_get_lines_domain(self, options):
        company_ids = self.env.company.ids
        domain = [
            ("state", "=", "posted"),
            ("journal_id.l10n_latam_use_documents", "=", True),
            ("company_id", "in", company_ids),
        ]
        if options.get("date").get("date_to"):
            domain += [("date", "<=", options["date"]["date_to"])]
        if options.get("date").get("date_from"):
            domain += [("date", ">=", options["date"]["date_from"])]
        return domain

    def _vat_simple_get_csv_move_ids(self, options, file_type):
        """All we care about are the ids of the moves we want to include in the report.
        As such, we can get only the ids instead of prefetch everything related to the records."""
        if options.get("all_entries"):
            raise UserError(
                _(
                    "Can only generate CSV files using posted entries."
                    ' Please remove "Include unposted entries" filter and try again'
                )
            )

        domain = [("l10n_latam_document_type_id.code", "!=", False)] + self._vat_simple_get_lines_domain(options)
        if file_type == "sale_invoice":
            domain += [("journal_id.type", "=", "sale"), ("move_type", "=", "out_invoice")]
        elif file_type == "sale_refund":
            domain += [("journal_id.type", "=", "sale"), ("move_type", "=", "out_refund")]
        elif file_type == "purchase_invoice":
            domain += [("journal_id.type", "=", "purchase"), ("move_type", "=", "in_invoice")]
        else:
            domain += [("journal_id.type", "=", "purchase"), ("move_type", "=", "in_refund")]
        return tuple(self.env["account.move"].search(domain, order="invoice_date asc, name asc, id asc").ids)

    def _vat_simple_transform_column(self, value):
        """ARCA requires all numbers to use ',' as decimal separator.
        Additionally, negative values are converted to positive (absolute value is taken)."""
        if isinstance(value, (int, float)):
            if value < 0:
                value = -value
            value = str(value)
        if "." in value:
            value = value.replace(".", ",")
        return value

    def _vat_simple_get_data(self, file_type, move_ids):
        if "sale_" in file_type:
            results = self._vat_simple_build_sale_query(file_type, move_ids)
        else:
            results = self._vat_simple_build_purchase_query(file_type, move_ids)

        fp = io.StringIO()
        headers = results[0].keys() if results else []
        writer = DictWriter(fp, fieldnames=headers, delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
        return fp.getvalue()

    def _vat_simple_get_taxes_from_row(self, row):
        """Taxes are not aggregated in the query, so we need to compute them manually."""
        aml_ids = row.get("aml_ids")
        total = row.get("balance")
        line_ids = self.env["account.move.line"].browse(aml_ids)

        currency_id = line_ids[:1].move_id.currency_id
        tax_data = line_ids.tax_ids.filtered("tax_group_id.l10n_ar_vat_afip_code").compute_all(
            total, currency=currency_id
        )
        return currency_id.round(tax_data["total_included"] - tax_data["total_excluded"])

    def _vat_simple_build_purchase_query(self, file_type, move_ids):
        columns_map = {
            "Concepto": "concept",
            "Codigo de Alicuota": "rate_code",
            "Monto Neto Gravado": "balance",
            "Credito Fiscal Facturado": "vat_amount",
        }
        if file_type == "purchase_invoice":
            # Additional column for vendor bills
            columns_map["Credito Fiscal Computable"] = "vat_amount"

        query = SQL(
            """
                WITH move_lines_with_concept AS (
                    SELECT DISTINCT ON (aml.id)
                        aml.*,
                        CASE
                            WHEN tag_rel.account_account_tag_id = %(lease_tag_id)s THEN 2
                            WHEN tag_rel.account_account_tag_id = %(fixed_tag_id)s THEN 4
                            WHEN pt.type = 'consu' THEN 1
                            WHEN pt.type = 'service' THEN 3
                            ELSE 1
                        END as concept,
                        btg.l10n_ar_vat_afip_code AS rate_code
                    FROM account_move_line aml
                    LEFT JOIN product_product pp ON aml.product_id = pp.id
                    LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    LEFT JOIN account_account_account_tag tag_rel
                        ON aml.account_id = tag_rel.account_account_id
                        AND tag_rel.account_account_tag_id IN (%(lease_tag_id)s, %(fixed_tag_id)s)
                    LEFT JOIN account_move_line_account_tax_rel amltr ON aml.id = amltr.account_move_line_id
                    LEFT JOIN account_tax bt ON amltr.account_tax_id = bt.id
                    LEFT JOIN account_tax_group btg ON bt.tax_group_id = btg.id
                    WHERE
                        aml.move_id IN %(move_ids)s AND
                        btg.l10n_ar_vat_afip_code IN ('3', '4', '5', '6', '8', '9') AND
                        aml.partner_id IS NOT NULL
                    ORDER BY
                        aml.id,
                        -- Prioritize lease tag over fixed asset tag for concept determination on the distinct selection
                        (CASE
                                WHEN tag_rel.account_account_tag_id = %(lease_tag_id)s THEN 1
                                WHEN tag_rel.account_account_tag_id = %(fixed_tag_id)s THEN 2
                                ELSE 3
                        END)
                )
                SELECT
                    concept,
                    rate_code,
                    SUM(balance) AS balance,
                    ARRAY_AGG(DISTINCT id) as aml_ids,
                    ARRAY_AGG(DISTINCT move_id) as move_ids
                FROM move_lines_with_concept
                GROUP BY concept, rate_code
                ORDER BY concept, rate_code;
            """,
            lease_tag_id=self.env.ref("l10n_ar_account_reports.tag_leases_rentals_account").id,
            fixed_tag_id=self.env.ref("l10n_ar_account_reports.tag_fixed_asset_account").id,
            move_ids=move_ids,
        )

        self.env.cr.execute(query)
        data = self.env.cr.dictfetchall()

        results = []
        for row in data:
            row_data = {}
            for header_name, column in columns_map.items():
                if column == "vat_amount":
                    value = self._vat_simple_get_taxes_from_row(row)
                else:
                    value = row.get(column, "")
                value = self._vat_simple_transform_column(value)
                row_data[header_name] = value
            results.append(row_data)
        return results

    def _vat_simple_build_sale_query(self, file_type, move_ids):
        columns_map = {
            "Actividad": "activity",
            "Tipo de Operacion": "operation_type",
            "Tipo de sujeto comprador": "responsibility_type_code",
            "Codigo de Alicuota": "rate_code",
            "Monto Neto Gravado": "balance",
        }
        if file_type == "sale_invoice":
            tag_id = self.env.ref("l10n_ar_account_reports.tag_fixed_asset_account")
            operation_type_query = SQL(
                """
                (CASE
                    WHEN btg.l10n_ar_vat_afip_code IN ('0', '1', '2') THEN 3
                    WHEN aaat.account_account_tag_id = %(tag_id)s THEN 2
                    ELSE 1
                END)
                """,
                tag_id=tag_id.id,
            )
            columns_map["Debito Fiscal Facturado"] = "vat_amount"
            columns_map["Debito Fiscal O.D.P."] = "vat_amount"
            exempt_operation_type = 3
            # Since we are SELECT DISTINCT ON, we need a stable ORDER BY. Prioritize fixed asset tag for the op type.
            cte_order_query = SQL(
                "ORDER BY aml.id, (CASE when aaat.account_account_tag_id = %(tag_id)s THEN 1 ELSE 2 END)",
                tag_id=tag_id.id,
            )
        else:
            operation_type_query = SQL(
                """
                (CASE
                    WHEN btg.l10n_ar_vat_afip_code IN %(code_values)s THEN 2
                    ELSE 1
                END)
                """,
                code_values=("0", "1", "2"),
            )
            columns_map["Debito Fiscal a Restituir"] = "vat_amount"
            exempt_operation_type = 2
            cte_order_query = SQL("ORDER BY aml.id")
        columns_map["Monto Neto Exento o No Gravado"] = "exempt_balance"

        query = SQL(
            """
                WITH move_lines_with_operation_type AS (
                    SELECT DISTINCT ON (aml.id)
                        aml.balance,
                        aml.id,
                        aml.move_id,
                        COALESCE(amlact.code, cmpact.code, '0') AS activity,
                        %(operation_query)s AS operation_type,
                        rprt.code as partner_responsibility_code,
                        btg.l10n_ar_vat_afip_code
                    FROM account_move_line aml
                    LEFT JOIN account_account acc ON aml.account_id = acc.id
                    LEFT JOIN afip_activity amlact ON acc.l10n_ar_afip_activity_id = amlact.id
                    LEFT JOIN res_company cmp ON aml.company_id = cmp.id
                    LEFT JOIN afip_activity cmpact ON cmp.l10n_ar_afip_activity_id = cmpact.id
                    LEFT JOIN account_account_account_tag aaat ON acc.id = aaat.account_account_id
                    LEFT JOIN res_partner rp ON aml.partner_id = rp.id
                    LEFT JOIN l10n_ar_afip_responsibility_type rprt ON rp.l10n_ar_afip_responsibility_type_id = rprt.id
                    LEFT JOIN account_move_line_account_tax_rel amltr ON aml.id = amltr.account_move_line_id
                    LEFT JOIN account_tax bt ON amltr.account_tax_id = bt.id
                    LEFT JOIN account_tax_group btg ON bt.tax_group_id = btg.id
                    WHERE
                        btg.l10n_ar_vat_afip_code IS NOT NULL AND aml.move_id IN %(move_ids)s
                        %(cte_order_query)s
                )
                SELECT
                    activity,
                    operation_type,
                    operation_type = %(exempt_op_type)s AS is_exempt,
                    CASE
                        WHEN operation_type = %(exempt_op_type)s THEN ''
                        WHEN partner_responsibility_code = '1' THEN '1'
                        WHEN partner_responsibility_code IN ('6', '13') THEN '2'
                        WHEN partner_responsibility_code IN ('4', '5', '7', '8', '9', '10', '16') THEN '3'
                        ELSE ''
                    END AS responsibility_type_code,
                    CASE
                        WHEN operation_type = %(exempt_op_type)s THEN ''
                        ELSE l10n_ar_vat_afip_code
                    END AS rate_code,
                    SUM(balance) AS balance,
                    ARRAY_AGG(DISTINCT id) as aml_ids,
                    ARRAY_AGG(DISTINCT move_id) as move_ids
                FROM move_lines_with_operation_type
                GROUP BY activity, operation_type, responsibility_type_code, rate_code
                ORDER BY activity, operation_type, responsibility_type_code, rate_code;
            """,
            operation_query=operation_type_query,
            cte_order_query=cte_order_query,
            exempt_op_type=exempt_operation_type,
            move_ids=move_ids,
        )

        self.env.cr.execute(query)
        data = self.env.cr.dictfetchall()
        exempt_columns = ["Actividad", "Tipo de Operacion", "Monto Neto Exento o No Gravado"]

        results = []
        for row in data:
            row_data = {}
            for header_name, column in columns_map.items():
                if row["is_exempt"] and header_name not in exempt_columns:
                    value = ""
                elif column == "vat_amount":
                    value = self._vat_simple_get_taxes_from_row(row)
                elif column == "exempt_balance":
                    # Solo mostrar balance si es operación exenta
                    value = row.get("balance", "") if row["is_exempt"] else ""
                elif column == "balance":
                    # No mostrar balance en "Monto Neto Gravado" si es operación exenta
                    value = "" if row["is_exempt"] else row.get("balance", "")
                else:
                    value = row.get(column, "")
                value = self._vat_simple_transform_column(value)
                row_data[header_name] = value
            results.append(row_data)
        return results
