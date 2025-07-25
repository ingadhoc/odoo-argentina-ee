# spelling: ignore ventas costo gastos comercializacion administracion eerr resultados financieros
# spelling: ignore otros ingresos egresos impuesto ganancias Estado caja bancos inversiones temporarias
# spelling: ignore creditos bienes cambio activos llave negocio deudas comerciales prestamos
# spelling: ignore remun cargas sociales fiscales anticipos clientes dividendos pagar previsiones
# spelling: ignore patrimonio neto sociedades participaciones intangibles

##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _load(self, template_code, company, install_demo, force_create=True):
        # Call the original method first
        res = super()._load(template_code, company, install_demo, force_create)

        # Verify that it's an Argentine chart of accounts
        # Check if applicable to "ar_ex", "ar_base"
        if template_code in [
            "ar_ri",
        ]:
            self._l10n_ar_account_reports_setup_account_tags([company])

        return res

    def _get_ar_account_tags(self):
        """Get all account tags defined in l10n_ar_account_reports

        This method returns tags for:
        - Income Statement (Estado de Resultados)
        - Balance Sheet (Estado Patrimonial)
        """
        tags = {
            # Income Statement tags (Estado de Resultados)
            "ventas": self.env.ref("l10n_ar_account_reports.ar_eerr_ventas"),
            "costo_ventas": self.env.ref("l10n_ar_account_reports.ar_eerr_costo_ventas"),
            "gastos_comercializacion": self.env.ref("l10n_ar_account_reports.ar_eerr_gastos_comercializacion"),
            "gastos_administracion": self.env.ref("l10n_ar_account_reports.ar_eerr_gastos_administracion"),
            "otros_gastos": self.env.ref("l10n_ar_account_reports.ar_eerr_otros_gastos"),
            "resultados_financieros": self.env.ref("l10n_ar_account_reports.ar_eerr_rxt_resultados_financieros"),
            "otros_ingresos_egresos": self.env.ref("l10n_ar_account_reports.ar_eerr_otros_ingresos_egresos"),
            "impuesto_ganancias": self.env.ref("l10n_ar_account_reports.ar_eerr_impuesto_ganancias"),
            # Balance Sheet tags (Estado Patrimonial)
            "caja_bancos": self.env.ref("l10n_ar_account_reports.ar_esp_caja_y_bancos"),
            "inversiones_temporarias": self.env.ref("l10n_ar_account_reports.ar_esp_inversiones_temporarias"),
            "creditos_ventas": self.env.ref("l10n_ar_account_reports.ar_esp_creditos_por_ventas"),
            "otros_creditos": self.env.ref("l10n_ar_account_reports.ar_esp_otros_creditos"),
            "bienes_cambio": self.env.ref("l10n_ar_account_reports.ar_esp_bienes_de_cambio"),
            "otros_activos": self.env.ref("l10n_ar_account_reports.ar_esp_otros_activos"),
            "creditos_ventas_nc": self.env.ref("l10n_ar_account_reports.ar_esp_creditos_por_ventas_nc"),
            "otros_creditos_nc": self.env.ref("l10n_ar_account_reports.ar_esp_otros_creditos_nc"),
            "bienes_cambio_nc": self.env.ref("l10n_ar_account_reports.ar_esp_bienes_de_cambio_nc"),
            "bienes_uso": self.env.ref("l10n_ar_account_reports.ar_esp_bienes_de_uso"),
            "participaciones_sociedades": self.env.ref("l10n_ar_account_reports.ar_esp_participaciones_en_sociedades"),
            "otras_inversiones_nc": self.env.ref("l10n_ar_account_reports.ar_esp_otras_inversiones_nc"),
            "activos_intangibles": self.env.ref("l10n_ar_account_reports.ar_esp_activos_intangibles"),
            "otros_activos_nc": self.env.ref("l10n_ar_account_reports.ar_esp_otros_activos_nc"),
            "llave_negocio": self.env.ref("l10n_ar_account_reports.ar_esp_llave_de_negocio"),
            "deudas_comerciales": self.env.ref("l10n_ar_account_reports.ar_esp_deudas_comerciales"),
            "prestamos": self.env.ref("l10n_ar_account_reports.ar_esp_prestamos"),
            "remun_cargas_sociales": self.env.ref("l10n_ar_account_reports.ar_esp_remun_y_cargas_sociales"),
            "cargas_fiscales": self.env.ref("l10n_ar_account_reports.ar_esp_cargas_fiscales"),
            "anticipos_clientes": self.env.ref("l10n_ar_account_reports.ar_esp_anticipos_de_clientes"),
            "dividendos_pagar": self.env.ref("l10n_ar_account_reports.ar_esp_dividendos_a_pagar"),
            "otras_deudas": self.env.ref("l10n_ar_account_reports.ar_esp_otras_deudas"),
            "previsiones": self.env.ref("l10n_ar_account_reports.ar_esp_previsiones"),
            "deudas_nc": self.env.ref("l10n_ar_account_reports.ar_esp_deudas_no_corrientes"),
            "previsiones_nc": self.env.ref("l10n_ar_account_reports.ar_esp_previsiones_no_corrientes"),
            # 'part_terceros': self.env.ref("l10n_ar_account_reports.ar_esp_part_terceros_en_soc"),
            "patrimonio_neto": self.env.ref("l10n_ar_account_reports.ar_esp_patrimonio_neto"),
        }
        return tags

    def _get_tag_for_income_account(self, account, tags):
        """Determine tag for income accounts"""
        code = account.code
        name = account.name.lower() if account.name else ""

        # Special cases based on specific CSV codes
        if code in ["999997", "999000000001"] or "ganancia por diferencia" in name or "descuento de efectivo" in name:
            return tags["resultados_financieros"].id
        elif code in ["999998", "999000000002"] or "pérdida por diferencia" in name:
            return tags["otros_ingresos_egresos"].id

        # Sales (Ventas) (4.1.1.xx.xxx)
        if account.account_type == "income" or (code and code.startswith("4.1.1")):
            return tags["ventas"].id

        # Cost of Sales (Costo de Ventas) (5.1.1.xx.xxx)
        elif account.account_type == "expense_direct_cost" or (code and code.startswith("5.1.1")):
            return tags["costo_ventas"].id

        # Classification by code for expenses
        elif account.account_type in ["expense", "expense_depreciation"]:
            # Sales expenses (Gastos de comercialización) (5.2.1.xx.xxx)
            if code and code.startswith("5.2"):
                return tags["gastos_comercializacion"].id
            # Administrative expenses (Gastos de administración) (5.3.1.xx.xxx)
            elif code and code.startswith("5.3"):
                return tags["gastos_administracion"].id
            # Financial results (Resultados financieros) (5.6.1.xx.xxx except 5.6.1.01.060)
            elif code and code.startswith("5.6") and not code.startswith("5.6.1.01.060"):
                return tags["resultados_financieros"].id
            # Various taxes (Impuestos varios) (5.4.x.xx.xxx)
            elif code and code.startswith("5.4"):
                return tags["otros_gastos"].id
            # Depreciation (Depreciaciones) (5.7.1.xx.xxx)
            elif code and code.startswith("5.7"):
                return tags["otros_gastos"].id
            # Bank expenses (Gastos bancarios) (5.6.1.01.060)
            elif code and code == "5.6.1.01.060":
                return tags["otros_gastos"].id
            # Production expenses (Gastos de producción) (5.1.2.xx.xxx)
            elif code and code.startswith("5.1.2"):
                return tags["otros_gastos"].id
            # Other expenses by default
            else:
                return tags["otros_gastos"].id

        # Other income/expenses
        elif account.account_type == "income_other":
            # Exchange differences (Diferencias de cambio)
            if code and code == "4.2.1.01.020":
                return tags["resultados_financieros"].id
            # Other income (Otros ingresos)
            else:
                return tags["otros_ingresos_egresos"].id

        # Income tax (Impuesto a las ganancias) (5.5.x.xx.xxx)
        if code and (code.startswith("5.5") or ("impuesto" in name and "ganancias" in name)):
            return tags["impuesto_ganancias"].id

        return None

    def _get_tag_for_asset_account(self, account, tags):
        """Determine tag for asset accounts"""
        code = account.code

        # Special cases based on the CSV
        if code and (
            code.startswith("1.1.1.02.003")
            or code.startswith("1.1.1.02.004")
            or code.startswith("1.1.1.02.007")
            or code.startswith("1.1.1.02.008")
        ):
            return tags["otros_creditos"].id

        if code and code == "1.1.6.01.050":  # Supplier Advances (Anticipo a Proveedores)
            return tags["otros_creditos"].id

        # Cash and Banks (Caja y Bancos) (1.1.1.xx.xxx)
        if account.account_type == "asset_cash" or (code and code.startswith("1.1.1")):
            return tags["caja_bancos"].id

        # Temporary investments (Inversiones temporarias) (1.1.2.xx.xxx)
        elif code and code.startswith("1.1.2"):
            return tags["inversiones_temporarias"].id

        # Trade receivables (Créditos por ventas) (1.1.3.xx.xxx)
        elif account.account_type == "asset_receivable" or (code and code.startswith("1.1.3")):
            return tags["creditos_ventas"].id

        # Other credits (Otros créditos) (1.1.4.xx.xxx, 1.1.5.xx.xxx)
        elif code and (code.startswith("1.1.4") or code.startswith("1.1.5")):
            return tags["otros_creditos"].id

        # Inventory (Bienes de cambio) (1.1.6.xx.xxx)
        elif code and code.startswith("1.1.6"):
            return tags["bienes_cambio"].id

        # Non-current assets
        elif code and code.startswith("1.2"):
            # The CSV has an error, accounts 1.2.1.* should be Fixed Assets (Bienes de Uso)
            if code.startswith("1.2.1"):
                return tags["bienes_uso"].id
            # The CSV has an error, accounts 1.2.2.* should be Intangible Assets (Activos Intangibles)
            elif code.startswith("1.2.2"):
                return tags["activos_intangibles"].id

        # Classification by account type for uncovered cases
        if account.account_type == "asset_current":
            return tags["otros_activos"].id
        elif account.account_type == "asset_non_current":
            return tags["otros_activos_nc"].id

        return None

    def _get_tag_for_liability_equity_account(self, account, tags):
        """Determine tag for liability and equity accounts"""
        code = account.code
        name = account.name.lower() if account.name else ""

        # Special case for account 9.9.9.99.999
        if code == "9.9.9.99.999":
            return tags["cargas_fiscales"].id

        # Customer advances (Anticipos de clientes)
        if code and code == "2.1.1.01.040" or ("anticipo" in name and "cliente" in name):
            return tags["anticipos_clientes"].id

        # Loans (Préstamos)
        if code and code == "2.1.2.01.040":
            return tags["prestamos"].id

        # Equity (Patrimonio Neto) (3.x.x.xx.xxx)
        if account.account_type == "equity" or (code and code.startswith("3")):
            return tags["patrimonio_neto"].id

        # Trade payables (Deudas Comerciales) (2.1.1.xx.xxx)
        elif account.account_type == "liability_payable" or (code and code.startswith("2.1.1")):
            return tags["deudas_comerciales"].id

        # Salaries and social charges (Remuneraciones y cargas sociales) (2.1.4.xx.xxx)
        elif code and code.startswith("2.1.4"):
            return tags["remun_cargas_sociales"].id

        # Tax liabilities (Cargas fiscales) (2.1.3.xx.xxx)
        elif code and code.startswith("2.1.3"):
            return tags["cargas_fiscales"].id

        # Other debts (Otras deudas) (2.1.2.xx.xxx, 2.1.5.xx.xxx)
        elif code and (code.startswith("2.1.2") or code.startswith("2.1.5")):
            return tags["otras_deudas"].id

        # Non-current debts (Deudas no corrientes) (2.2.1.xx.xxx)
        elif code and code.startswith("2.2.1"):
            return tags["deudas_nc"].id

        # Provisions (Previsiones) (2.2.2.xx.xxx)
        elif code and code.startswith("2.2.2"):
            return tags["previsiones"].id

        # Classification by account type for uncovered cases
        if account.account_type == "liability_current":
            return tags["otras_deudas"].id
        elif account.account_type == "liability_non_current":
            return tags["deudas_nc"].id

        return None

    def _l10n_ar_account_reports_setup_account_tags(self, ar_companies):
        """Set up account tags for Argentine chart templates"""
        tags = self._get_ar_account_tags()

        for company in ar_companies:
            # En Odoo 18, las cuentas usan company_ids (many2many) en lugar de company_id
            accounts = self.env["account.account"].search([("company_ids", "in", company.id)])

            for account in accounts:
                tag_id = None

                # Income statement accounts
                if account.account_type in [
                    "income",
                    "expense",
                    "expense_direct_cost",
                    "expense_depreciation",
                    "income_other",
                ]:
                    tag_id = self._get_tag_for_income_account(account, tags)

                # Asset accounts
                elif account.account_type in ["asset_cash", "asset_receivable", "asset_current", "asset_non_current"]:
                    tag_id = self._get_tag_for_asset_account(account, tags)

                # Liability and equity accounts
                elif account.account_type in [
                    "liability_payable",
                    "liability_current",
                    "liability_non_current",
                    "equity",
                ]:
                    tag_id = self._get_tag_for_liability_equity_account(account, tags)

                # Assign the tag if one was found
                if tag_id:
                    account.write({"tag_ids": [(4, tag_id)]})
