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
        if company.account_fiscal_country_id.code == "AR":
            self._l10n_ar_account_reports_setup_account_tags([company])

        return res

    def _post_load_data(self, template_code, company, template_data):
        super()._post_load_data(template_code, company, template_data)
        if company.account_fiscal_country_id.code == "AR":
            self._l10n_ar_account_reports_setup_account_tags([company])

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
            "capital": self.env.ref("l10n_ar_account_reports.ar_esp_capital"),
            "reservas": self.env.ref("l10n_ar_account_reports.ar_esp_reservas"),
            "resultados": self.env.ref("l10n_ar_account_reports.ar_esp_resultados"),
            "resultado_del_ejercicio": self.env.ref("l10n_ar_account_reports.ar_esp_resultado_del_ejercicio"),
        }
        return tags

    def _get_tag_for_income_account(self, account, tags, company):
        """Determine tag for income accounts"""
        code = account.with_company(company).code
        name = account.name.lower() if account.name else ""

        # Special cases based on specific CSV codes
        if code and code.startswith("999") and account.account_type == "income_other":
            return tags["resultados_financieros"].id
        elif code and code.startswith("999") and account.account_type == "expense":
            return tags["otros_ingresos_egresos"].id
        elif code and code.startswith("5.6.1") and account.account_type == "expense" and "r.e.c.p.a.m." in name:
            return tags["resultados_financieros"].id

        # Sales (Ventas) (4.1.1.xx.xxx)
        if account.account_type == "income" or (code and code.startswith("4.1.1")):
            return tags["ventas"].id

        # Cost of Sales (Costo de Ventas) (5.1.1.xx.xxx)
        elif account.account_type == "expense_direct_cost" or (code and code.startswith("5.1.1")):
            return tags["costo_ventas"].id

        # Classification by code for expenses
        elif account.account_type in ["expense", "expense_depreciation"]:
            # Sales expenses (Gastos de comercialización) (5.2.1.xx.xxx)
            if code and code.startswith("5.1.1"):
                return tags["costo_ventas"].id
            # Sales expenses (Gastos de comercialización) (5.2.1.xx.xxx)
            elif code and code.startswith("5.2"):
                return tags["gastos_comercializacion"].id
            # Administrative expenses (Gastos de administración) (5.3.1.xx.xxx)
            elif code and code.startswith("5.3"):
                return tags["gastos_administracion"].id
            # Financial results (Resultados financieros) (5.6.1.xx.xxx except 5.6.1.01.060)
            elif (
                code
                and code.startswith("5.6")
                and not any(keyword in name for keyword in ["gastos bancarios", "bank charges"])
            ):
                return tags["resultados_financieros"].id
            elif code and code.startswith("5.5"):
                return tags["impuesto_ganancias"].id
            else:
                return tags["otros_gastos"].id

        # Other income/expenses
        elif account.account_type == "income_other":
            # Exchange differences (Diferencias de cambio)
            if code and (code.startswith("4.2.1") or code.startswith("4.3.1")):
                if any(keyword in name for keyword in ["diferencias de cambio", "exchange differences"]):
                    return tags["resultados_financieros"].id
                else:
                    return tags["otros_ingresos_egresos"].id

        return None

    def _get_tag_for_asset_account(self, account, tags, company):
        """Determine tag for asset accounts"""
        code = account.with_company(company).code
        name = account.name.lower() if account.name else ""

        # Cash and Banks (Caja y Bancos) (1.1.1.xx.xxx)
        if account.account_type == "asset_cash":
            if code and code.startswith("6."):
                return None
            return tags["caja_bancos"].id

        # Temporary investments (Inversiones temporarias) (1.1.2.xx.xxx)
        if code and code.startswith("1.1.2"):
            return tags["inversiones_temporarias"].id

        # Account current (Activos corrientes)
        if account.account_type == "asset_current":
            # Cuentas pendientes y transitorias
            if code and code.startswith("1.1.1"):
                if any(keyword in name for keyword in ["pendientes", "pending", "outstanding"]):
                    return tags["otros_creditos"].id
                else:
                    return tags["caja_bancos"].id

            # Credit sales (Ventas a crédito) (1.1.3.xx.xxx)
            if code and code.startswith("1.1.3"):
                return tags["creditos_ventas"].id

            # Other credits (Otros créditos) (1.1.4.xx.xxx, 1.1.5.xx.xxx)
            elif code and (code.startswith("1.1.4") or code.startswith("1.1.5")):
                return tags["otros_creditos"].id

            # Inventory (Bienes de cambio) (1.1.6.xx.xxx)
            elif code and code.startswith("1.1.6") and any(keyword in name for keyword in ["anticipo", "advances"]):
                return tags["otros_creditos"].id
            elif code and code.startswith("1.1.6"):
                return tags["bienes_cambio"].id

            return None

        # Non-current assets
        elif code and code.startswith("1.2"):
            return tags["bienes_uso"].id

        # Asset receivable accounts (Por cobrar)
        if account.account_type == "asset_receivable":
            if code and code.startswith("1.1.3"):
                return tags["creditos_ventas"].id
            else:
                return tags["otros_creditos"].id
        elif account.account_type == "asset_non_current":
            return tags["otros_activos_nc"].id

        elif account.account_type == "asset_fixed":
            return tags["bienes_uso"].id

        return None

    def _get_tag_for_liability_equity_account(self, account, tags, company):
        """Determine tag for liability and equity accounts"""
        code = account.with_company(company).code
        name = account.name.lower() if account.name else ""

        # Equity (Patrimonio Neto) (3.x.x.xx.xxx)
        if any(keyword in name for keyword in ["loan", "prestamo"]):
            return tags["prestamos"].id

        elif code and code.startswith("3.1"):
            return tags["capital"].id
        elif code and code.startswith("3.2"):
            return tags["reservas"].id
        elif code and code.startswith("3.3") and account.account_type == "equity_unaffected":
            return tags["resultado_del_ejercicio"].id
        elif code and code.startswith("3.3"):
            return tags["resultados"].id
        # Pasivos no circulantes
        if account.account_type in ["liability_current", "liability_payable"]:
            if code and code.startswith("1.1.1"):
                return tags["otros_creditos"].id
            if code and code.startswith("2.1.1") and any(keyword in name for keyword in ["anticipos", "advances"]):
                return tags["anticipos_clientes"].id
            elif code and code.startswith("2.1.1"):
                return tags["deudas_comerciales"].id
            elif code and code.startswith("2.1.2"):
                return tags["otras_deudas"].id
            elif code and code.startswith("2.1.3"):
                return tags["cargas_fiscales"].id
            elif code and code.startswith("2.1.4"):
                return tags["remun_cargas_sociales"].id
            elif code and code.startswith("2.2.2"):
                return tags["previsiones"].id
            elif code and code.startswith("9.9.9"):
                return tags["cargas_fiscales"].id

        elif account.account_type == "liability_non_current":
            if code and code.startswith("2.1.5"):
                return tags["otras_deudas"].id
            else:
                return tags["deudas_nc"].id

        return None

    def _l10n_ar_account_reports_setup_account_tags(self, ar_companies):
        """Set up account tags for Argentine chart templates"""
        tags = self._get_ar_account_tags()
        tag_ids = list(tags.values())
        tag_ids_list = [tag.id for tag in tag_ids]  # Lista de IDs de todas las etiquetas

        for company in ar_companies:
            # En Odoo 18, las cuentas usan company_ids (many2many) en lugar de company_id
            accounts = self.env["account.account"].search([("company_ids", "in", company.id)])

            # Primero limpiar todas las etiquetas específicas de reportes argentinos
            for account in accounts:
                # Quitar todas las etiquetas argentinas existentes
                for tag_id in tag_ids_list:
                    account.write({"tag_ids": [(3, tag_id)]})

            # Luego asignar las etiquetas correctas
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
                    tag_id = self._get_tag_for_income_account(account, tags, company)

                # Asset accounts
                elif account.account_type in [
                    "asset_cash",
                    "asset_receivable",
                    "asset_current",
                    "asset_non_current",
                    "asset_fixed",
                ]:
                    tag_id = self._get_tag_for_asset_account(account, tags, company)

                # Liability and equity accounts
                elif account.account_type in [
                    "liability_payable",
                    "liability_current",
                    "liability_non_current",
                    "equity",
                    "equity_unaffected",
                ]:
                    tag_id = self._get_tag_for_liability_equity_account(account, tags, company)

                # Assign the tag if one was found
                if tag_id:
                    account.write({"tag_ids": [(4, tag_id)]})
