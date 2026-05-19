import io
from datetime import datetime

import xlwt
from odoo import http
from odoo.http import content_disposition, request


class GenerateXLS(http.Controller):
    @http.route("/account_balance_import/partner_balance_xls", type="http", auth="user")
    def generate_partner_balance_xls(self, company_id, date, balance_type, export_partners, import_type="absolute"):
        """Generate a XLS file with partner balances.

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
        workbook = xlwt.Workbook(encoding="utf8")
        style = xlwt.easyxf("pattern: pattern solid, fore_colour light_yellow")
        date_style = xlwt.easyxf(num_format_str="YYYY-MM-DD")
        sheet = workbook.add_sheet("Partner Balance Import")

        # Adjust column width
        sheet.col(0).width = 256 * 40  # Nombre / CUIT / Referencia Interna
        sheet.col(1).width = 256 * 30  # Referencia / Documento
        sheet.col(2).width = 256 * 15  # Importe
        sheet.col(3).width = 256 * 25  # Fecha de Vencimiento
        sheet.col(4).width = 256 * 20  # Otra Moneda
        sheet.col(5).width = 256 * 25  # Importe en Otra moneda

        # Write headers
        sheet.write(0, 0, "Nombre / CUIT / Referencia Interna", style)
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

        # Create a bytes stream
        f = io.BytesIO()
        workbook.save(f)
        f.seek(0)

        return request.make_response(
            f.getvalue(),
            [
                ("Content-Type", "application/octet-stream"),
                ("Content-Disposition", content_disposition("partner_balance.xls")),
            ],
        )
