# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10n_ArTaxReportHandler(models.AbstractModel):
    _inherit = "l10n_ar.tax.report.handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Add export button
        export_buttons = [
            {
                "name": "Retenciones de IVA sufridas",
                "sequence": 30,
                "action": "export_file",
                "action_param": "ret_iva_sufridas_txt",
                "file_export_type": "TXT",
            },
            {
                "name": "Percepciones de IVA sufridas",
                "sequence": 30,
                "action": "export_file",
                "action_param": "perc_iva_sufridas_txt",
                "file_export_type": "TXT",
            },
        ]

        options["buttons"].extend(export_buttons)

    def ret_iva_sufridas_txt(self, options):
        return {
            "file_name": "Retenciones IVA Sufridas.txt",
            "file_content": self._misiones_book_get_txt_files(options),
            "file_type": "txt",
        }

<<<<<<< ca55ed65e8d6136d320e8bbfde7b906dcb4835ae
    def perc_iva_sufridas_txt(self, options):
        return {
            "file_name": "Percepciones IVA Sufridas.txt",
            "file_content": self._misiones_book_get_txt_files(options),
            "file_type": "txt",
||||||| 2323f13f60ff7485868663935083aa8b1af273c4
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
        tax_data = line_ids.tax_ids.compute_all(total, currency=currency_id)
        return currency_id.round(tax_data["total_included"] - tax_data["total_excluded"])

    def _vat_simple_build_purchase_query(self, file_type, move_ids):
        columns_map = {
            "Concepto": "concept",
            "Codigo de Alicuota": "rate_code",
            "Monto Neto Gravado": "balance",
            "Credito Fiscal Facturado": "vat_amount",
=======
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
>>>>>>> 9b782a46537567b7feaf6b12f94824d5d94b4da7
        }
