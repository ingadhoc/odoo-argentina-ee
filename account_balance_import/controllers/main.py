import io
from datetime import datetime

import xlsxwriter
from odoo import http
from odoo.http import request
from odoo.http.stream import content_disposition


class GenerateXLS(http.Controller):
    @http.route("/account_balance_import/partner_balance_xls", type="http", auth="user")
    def generate_partner_balance_xls(self, company_id, date, balance_type, export_partners, import_type="absolute"):
        """Generate a XLSX file with partner balances.

        Args:
            company_id: Company ID
            date: Accounting date (YYYY-MM-DD)
            balance_type: 'receivable' or 'payable'
            export_partners: '1' to include existing partners, empty otherwise
            import_type: 'absolute' (no balances) or 'adjust' (with current balances)
        """
        company_id = int(company_id)
        company = request.env["res.company"].browse(company_id)

        # Parse date
        if date:
            accounting_date = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            accounting_date = datetime.today().date()

        # Create workbook
        f = io.BytesIO()
        workbook = xlsxwriter.Workbook(f, {"in_memory": True})
        style = workbook.add_format({"pattern": 1, "bg_color": "#FFFF99"})
        date_style = workbook.add_format({"num_format": "YYYY-MM-DD"})
        sheet = workbook.add_worksheet("Partner Balance Import")

        # Adjust column width
        sheet.set_column(0, 0, 40)  # Nombre / CUIT / Referencia Interna
        sheet.set_column(1, 1, 30)  # Referencia / Documento
        sheet.set_column(2, 2, 15)  # Importe
        sheet.set_column(3, 3, 25)  # Fecha de Vencimiento
        sheet.set_column(4, 4, 20)  # Otra Moneda
        sheet.set_column(5, 5, 25)  # Importe en Otra moneda

        # Write headers
        identifier_header = "Nombre / CUIT / Referencia Interna"
        if "internal_code" in request.env["res.partner"]._fields:
            identifier_header += " / Código Interno"
        sheet.write(0, 0, identifier_header, style)
        sheet.write(0, 1, "Referencia / Documento", style)
        sheet.write(0, 2, "Importe", style)
        if import_type != "adjust":
            sheet.write(0, 3, "Fecha de Vencimiento (Opcional)", style)
            sheet.write(0, 4, "Otra Moneda (Opcional)", style)
            sheet.write(0, 5, "Importe en Otra moneda (Opcional)", style)

        row_idx = 1

        # If export_partners is set, fetch partners
        if export_partners:
            # Build partner domain based on balance_type
            # receivable -> customers, payable -> suppliers
            partner_domain = [("company_id", "in", [False, company_id])]
            if balance_type == "receivable":
                partner_domain.append(("customer_rank", ">", 0))
            else:
                partner_domain.append(("supplier_rank", ">", 0))

            partners = request.env["res.partner"].with_company(company_id).search(partner_domain)

            # Get balances only if import_type is 'adjust'
            balances = {}
            if import_type == "adjust":
                wizard = request.env["account.balance_import_wizard"]
                balances = wizard._get_partners_balances_at_date(partners, accounting_date, balance_type, company)

            # Write partner rows
            for partner in partners:
                balance = balances.get(partner.id, 0.0)

                # For adjust mode, skip partners with zero balance
                if import_type == "adjust" and company.currency_id.is_zero(balance):
                    continue

                # Use VAT or ref or name as identifier
                identifier = partner.vat or partner.ref or partner.name

                sheet.write(row_idx, 0, identifier)
                sheet.write(row_idx, 1, f"Saldo Inicial {partner.name}")
                # For absolute mode, leave amount empty for user to fill
                # For adjust mode, show current balance
                sheet.write(row_idx, 2, balance if import_type == "adjust" else "")
                if import_type != "adjust":
                    sheet.write(row_idx, 3, "", date_style)  # No due date
                    sheet.write(row_idx, 4, "")  # No other currency
                    sheet.write(row_idx, 5, "")  # No amount in other currency
                row_idx += 1

        workbook.close()
        suffix = "receivable" if balance_type == "receivable" else "payable"

        return request.make_response(
            f.getvalue(),
            [
                ("Content-Type", "application/octet-stream"),
                ("Content-Disposition", content_disposition(f"partner_balance_{suffix}.xlsx")),
            ],
        )

    @http.route("/account_balance_import/account_balance_xls", type="http", auth="user")
    def generate_account_balance_xls(self, company_id):
        """Generate a XLSX with the company chart, ready for the native records import.

        Args:
            company_id: Company ID, the active one in the web client
        """
        company = request.env["res.company"].browse(int(company_id))
        if company not in request.env.user.company_ids:
            raise request.not_found()
        accounts = (
            request.env["account.account"]
            .with_company(company)
            .search(
                [
                    ("company_ids", "in", company.id),
                    ("account_type", "not in", ("asset_receivable", "liability_payable")),
                ],
                order="code",
            )
        )
        multi_currency = request.env.user.has_group("base.group_multi_currency")

        f = io.BytesIO()
        workbook = xlsxwriter.Workbook(f, {"in_memory": True})
        style = workbook.add_format({"pattern": 1, "bg_color": "#FFFF99"})
        sheet = workbook.add_worksheet("Account Balance Import")
        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 15)
        sheet.set_column(2, 2, 50)
        sheet.set_column(3, 4, 22)

        # Accounts are matched by database id on import, or by code when the id is empty.
        headers = [".id", "code", "name", "opening_balance"]
        if multi_currency:
            headers.append("amount_in_currency")
        for col, header in enumerate(headers):
            sheet.write(0, col, header, style)

        for row, account in enumerate(accounts, 1):
            sheet.write(row, 0, account.id)
            sheet.write(row, 1, account.code or "")
            sheet.write(row, 2, account.name)
            sheet.write(row, 3, account.opening_balance)
            # Only accounts in another currency take it: on the others the import rejects it.
            if multi_currency and account.currency_id and account.currency_id != company.currency_id:
                sheet.write(row, 4, account.amount_in_currency)
        workbook.close()

        return request.make_response(
            f.getvalue(),
            [
                ("Content-Type", "application/octet-stream"),
                ("Content-Disposition", content_disposition("account_balance.xlsx")),
            ],
        )
