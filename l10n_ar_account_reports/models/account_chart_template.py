##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _load(self, template_code, company, install_demo, force_create=True):
        # Override
        super()._load(template_code, company, install_demo, force_create)

        # Configure account tags for Argentine chart templates
        if template_code in ["ar_ri", "ar_ex", "ar_base"]:
            self._l10n_ar_account_reports_setup_account_tags([company])

    def _get_ar_account_tags(self):
        """Get all account tags defined in l10n_ar_account_reports"""
        tags = {
            # Estado de Resultados (Income Statement) tags
            "ventas": self.env.ref("l10n_ar_account_reports.ar_eerr_ventas"),
            "costo_ventas": self.env.ref("l10n_ar_account_reports.ar_eerr_costo_ventas"),
            "gastos_comercializacion": self.env.ref("l10n_ar_account_reports.ar_eerr_gastos_comercializacion"),
            "gastos_administracion": self.env.ref("l10n_ar_account_reports.ar_eerr_gastos_administracion"),
            "otros_gastos": self.env.ref("l10n_ar_account_reports.ar_eerr_otros_gastos"),
            "resultados_financieros": self.env.ref("l10n_ar_account_reports.ar_eerr_rxt_resultados_financieros"),
            "otros_ingresos_egresos": self.env.ref("l10n_ar_account_reports.ar_eerr_otros_ingresos_egresos"),
            "impuesto_ganancias": self.env.ref("l10n_ar_account_reports.ar_eerr_impuesto_ganancias"),
            # Estado Patrimonial (Balance Sheet) tags
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

        if account.account_type == "income":
            # Ventas (Sales)
            return tags["ventas"].id
        elif account.account_type == "expense_direct_cost":
            # Costo de Ventas (Cost of Sales)
            return tags["costo_ventas"].id
        elif account.account_type in ["expense", "expense_depreciation"]:
            # Gastos clasificados por código
            if code.startswith("5.1"):
                return tags["gastos_comercializacion"].id
            elif code.startswith("5.2"):
                return tags["gastos_administracion"].id
            elif code.startswith("5.3"):
                return tags["resultados_financieros"].id
            elif code.startswith("5.4"):
                return tags["otros_gastos"].id
            else:
                return tags["otros_gastos"].id
        elif account.account_type == "income_other":
            # Otros Ingresos y Egresos
            return tags["otros_ingresos_egresos"].id

        # Caso especial para impuesto a las ganancias
        if code.startswith("5.5") or ("impuesto" in account.name.lower() and "ganancias" in account.name.lower()):
            return tags["impuesto_ganancias"].id

        return None

    def _get_tag_for_asset_account(self, account, tags):
        """Determine tag for asset accounts"""
        code = account.code

        if account.account_type == "asset_cash":
            # Caja y Bancos
            return tags["caja_bancos"].id
        elif account.account_type == "asset_receivable":
            # Créditos por Ventas
            return tags["creditos_ventas"].id
        elif account.account_type == "asset_current":
            # Clasificación por código para activos corrientes
            if code.startswith("1.1.2"):
                # Inversiones Temporarias
                return tags["inversiones_temporarias"].id
            elif code.startswith("1.1.4"):
                # Otros Créditos
                return tags["otros_creditos"].id
            elif code.startswith("1.1.5"):
                # Bienes de Cambio
                return tags["bienes_cambio"].id
            else:
                # Otros Activos
                return tags["otros_activos"].id
        elif account.account_type == "asset_non_current":
            # Clasificación por código para activos no corrientes
            if code.startswith("1.2.1"):
                # Créditos por Ventas NC
                return tags["creditos_ventas_nc"].id
            elif code.startswith("1.2.2"):
                # Otros Créditos NC
                return tags["otros_creditos_nc"].id
            elif code.startswith("1.2.3"):
                # Bienes de Cambio NC
                return tags["bienes_cambio_nc"].id
            elif code.startswith("1.2.4"):
                # Bienes de Uso
                return tags["bienes_uso"].id
            elif code.startswith("1.2.5"):
                # Participaciones en Sociedades
                return tags["participaciones_sociedades"].id
            elif code.startswith("1.2.6"):
                # Otras Inversiones NC
                return tags["otras_inversiones_nc"].id
            elif code.startswith("1.2.7"):
                # Activos Intangibles
                return tags["activos_intangibles"].id
            elif code.startswith("1.2.8"):
                # Llave de Negocio
                return tags["llave_negocio"].id
            else:
                # Otros Activos NC
                return tags["otros_activos_nc"].id

        return None

    def _get_tag_for_liability_equity_account(self, account, tags):
        """Determine tag for liability and equity accounts"""
        code = account.code

        if account.account_type == "liability_payable":
            # Deudas Comerciales
            return tags["deudas_comerciales"].id
        elif account.account_type == "liability_current":
            # Clasificación por código para pasivos corrientes
            if code.startswith("2.1.2"):
                # Préstamos
                return tags["prestamos"].id
            elif code.startswith("2.1.3"):
                # Remuneraciones y Cargas Sociales
                return tags["remun_cargas_sociales"].id
            elif code.startswith("2.1.4"):
                # Cargas Fiscales
                return tags["cargas_fiscales"].id
            elif code.startswith("2.1.5"):
                # Anticipos de Clientes
                return tags["anticipos_clientes"].id
            elif code.startswith("2.1.6"):
                # Dividendos a Pagar
                return tags["dividendos_pagar"].id
            elif code.startswith("2.1.8"):
                # Previsiones
                return tags["previsiones"].id
            else:
                # Otras Deudas
                return tags["otras_deudas"].id
        elif account.account_type == "liability_non_current":
            # Clasificación para pasivos no corrientes
            if code.startswith("2.2.2"):
                # Previsiones No Corrientes
                return tags["previsiones_nc"].id
            else:
                # Deudas No Corrientes
                return tags["deudas_nc"].id
        elif account.account_type == "equity":
            # Patrimonio Neto
            return tags["patrimonio_neto"].id

        return None

    def _l10n_ar_account_reports_setup_account_tags(self, ar_companies):
        """Set up account tags for Argentine chart templates"""
        tags = self._get_ar_account_tags()

        for company in ar_companies:
            # Get all accounts for this company
            accounts = self.env["account.account"].search([("company_ids", "any", [("id", "=", company.id)])])

            for account in accounts:
                # Try to find a tag based on account type and code
                tag_id = None

                # Determine tag based on account groups
                if account.account_type in [
                    "income",
                    "expense",
                    "expense_direct_cost",
                    "expense_depreciation",
                    "income_other",
                ]:
                    tag_id = self._get_tag_for_income_account(account, tags)
                elif account.account_type in ["asset_cash", "asset_receivable", "asset_current", "asset_non_current"]:
                    tag_id = self._get_tag_for_asset_account(account, tags)
                elif account.account_type in [
                    "liability_payable",
                    "liability_current",
                    "liability_non_current",
                    "equity",
                ]:
                    tag_id = self._get_tag_for_liability_equity_account(account, tags)

                # If special case for impuesto ganancias overrides normal categorization
                code = account.code
                if code.startswith("5.5") or (
                    "impuesto" in account.name.lower() and "ganancias" in account.name.lower()
                ):
                    tag_id = tags["impuesto_ganancias"].id

                # Assign the tag if one was found
                if tag_id:
                    account.write({"tag_ids": [(6, 0, [tag_id])]})
