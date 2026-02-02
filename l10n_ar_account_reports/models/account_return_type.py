##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import datetime

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.tools.misc import format_date

# Extended periods to include fortnightly (quincenal) for Argentina
L10N_AR_PERIODS = [
    ("fortnightly", "Fortnightly"),  # Quincenal
]

# Days per period for sub-monthly periodicities
L10N_AR_DAYS_PER_PERIOD = {
    "fortnightly": 15,
}


class AccountReturnType(models.Model):
    _inherit = "account.return.type"

    deadline_periodicity = fields.Selection(
        selection_add=L10N_AR_PERIODS,
    )
    default_deadline_periodicity = fields.Selection(
        selection_add=L10N_AR_PERIODS,
    )
    # le ponemos store porque en odoo es un campo solo related y si no hay cuenta bancaria no hay partner
    # issue en odoo: https://github.com/odoo/odoo/issues/240322
    # al final le sacamos también el related porque si no en el create no se guarda. Podria implementarse como compute
    # pero no vemos necesidad por el momento
    payment_partner_id = fields.Many2one(store=True, related=False)

    l10n_ar_account_id = fields.Many2one(
        comodel_name="account.account",
        string="AR Closing Account",
        company_dependent=True,
        domain="[('account_type', 'in', ('liability_payable', 'asset_receivable'))]",
        help="Account to use for the closing entry of this return type. "
        "If not set, the partner's payable/receivable account will be used.",
    )
    l10n_ar_is_simple_closing_return = fields.Boolean(
        string="AR Simple Closing",
        compute="_compute_l10n_ar_is_simple_closing_return",
        help="If enabled, this return type uses simplified closing logic: "
        "no carryover mechanism and no automatic tax_lock_date update.",
    )

    @api.depends("country_id")
    def _compute_l10n_ar_is_simple_closing_return(self):
        """Compute if this return type should use simple closing (no carryover, no tax_lock_date).
        Al libro de IVA también lo hacemos tipo 'simple' porque los carryover confunden,
        mezclan libre disponibilidad y saldo a favor, además crean líneas de neto que confunden.
        """
        for record in self:
            record.l10n_ar_is_simple_closing_return = record.country_id.code == "AR"

    def _get_periodicity_months_delay(self, company, date=None):
        """Returns the number of months separating two returns.
        For sub-monthly periods (like fortnightly), returns 0.
        Use _get_periodicity_days_delay for sub-monthly periods.
        """
        self.ensure_one()
        periodicity = self._get_periodicity(company)
        if periodicity in L10N_AR_DAYS_PER_PERIOD:
            return 0
        return super()._get_periodicity_months_delay(company, date=date)

    def _get_periodicity_days_delay(self, company):
        """Returns the number of days separating two returns for sub-monthly periods.
        Returns 0 for monthly or longer periods.
        """
        self.ensure_one()
        periodicity = self._get_periodicity(company)
        return L10N_AR_DAYS_PER_PERIOD.get(periodicity, 0)

    def _is_sub_monthly_period(self, company):
        """Returns True if the periodicity is sub-monthly (e.g., fortnightly)"""
        self.ensure_one()
        return self._get_periodicity(company) in L10N_AR_DAYS_PER_PERIOD

    def _get_period_boundaries(self, company_id, date, override_period_months=None, override_start_date=None):
        """Returns the boundaries of the period containing the provided date
        for this return type as a tuple (start, end).

        Extended to support sub-monthly periods like fortnightly.
        """
        self.ensure_one()

        # Check if this is a sub-monthly period (e.g., fortnightly)
        if self._is_sub_monthly_period(company_id) and not override_period_months:
            return self._get_sub_monthly_period_boundaries(company_id, date, override_start_date)

        return super()._get_period_boundaries(company_id, date, override_period_months, override_start_date)

    def _get_sub_monthly_period_boundaries(self, company_id, date, override_start_date=None):
        """Returns the boundaries for sub-monthly periods like fortnightly.
        For fortnightly periods:
        - First fortnight: day 1 to day 15 of the month
        - Second fortnight: day 16 to last day of the month

        :param company_id: the company for which to compute the boundaries
        :param date: the date for which we want to find the period
        :param override_start_date: optional start date override
        :return: tuple (start_date, end_date)
        """
        self.ensure_one()
        periodicity = self._get_periodicity(company_id)

        if periodicity == "fortnightly":
            day = date.day
            year = date.year
            month = date.month

            if day <= 15:
                # First fortnight: 1st to 15th
                start_date = datetime.date(year, month, 1)
                end_date = datetime.date(year, month, 15)
            else:
                # Second fortnight: 16th to end of month
                start_date = datetime.date(year, month, 16)
                # Get last day of month
                end_date = datetime.date(year, month, 1) + relativedelta(months=1, days=-1)

            return start_date, end_date

        # Fallback for other sub-monthly periods (if added in future)
        days_per_period = self._get_periodicity_days_delay(company_id)
        if days_per_period <= 0:
            # Should not happen, but fallback to monthly
            return super()._get_period_boundaries(
                company_id, date, override_period_months=1, override_start_date=override_start_date
            )

        # Generic sub-monthly calculation based on days
        if override_start_date:
            start_day = override_start_date.day
        else:
            start_day, _ = self._get_start_date_elements(company_id)

        # Calculate period number within the month
        day_offset = date.day - start_day
        period_number = day_offset // days_per_period

        start_date = datetime.date(date.year, date.month, start_day) + relativedelta(
            days=period_number * days_per_period
        )
        end_date = start_date + relativedelta(days=days_per_period - 1)

        # Ensure end_date doesn't exceed month boundary
        month_end = datetime.date(date.year, date.month, 1) + relativedelta(months=1, days=-1)
        if end_date > month_end:
            end_date = month_end

        return start_date, end_date

    def _get_period_name(
        self,
        main_company=None,
        period_from=None,
        period_to=None,
        start_day=1,
        start_month=1,
        minimal=False,
        lang_code=None,
    ):
        """Extended to support fortnightly period names."""
        if not self:
            return super()._get_period_name(
                main_company=main_company,
                period_from=period_from,
                period_to=period_to,
                start_day=start_day,
                start_month=start_month,
                minimal=minimal,
                lang_code=lang_code,
            )
        self.ensure_one()
        periodicity = self._get_periodicity(main_company)

        if period_from and period_to and periodicity == "fortnightly":
            # For fortnightly: show "1ra Quincena Mes Año" or "2da Quincena Mes Año"
            fortnight_num = 1 if period_from.day == 1 else 2
            month_name = format_date(self.env, period_from, date_format="LLLL", lang_code=lang_code)
            if minimal:
                # Short format: "1Q Dec" or "2Q Dec"
                month_short = format_date(self.env, period_from, date_format="LLL", lang_code=lang_code)
                return f"{fortnight_num}Q {month_short}"
            else:
                # Full format: "1ra Quincena Diciembre 2024" or "2da Quincena Diciembre 2024"
                ordinal = "1ra" if fortnight_num == 1 else "2da"
                return f"{ordinal} Quincena {month_name} {period_from.year}"

        return super()._get_period_name(
            main_company, period_from, period_to, start_day, start_month, minimal, lang_code
        )

    def _get_l10n_ar_activity_domain(self):
        """Returns the domain to detect activity for this return type.
        This domain is used both for automatic return generation and for the closing entry.
        """
        self.ensure_one()
        external_id = self.get_external_id().get(self.id)
        if external_id == "l10n_ar_account_reports.ar_caba_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "C"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        if external_id == "l10n_ar_account_reports.ar_pba_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "B"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        if external_id == "l10n_ar_account_reports.ar_mendoza_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "M"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        if external_id == "l10n_ar_account_reports.ar_misiones_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "N"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        if external_id == "l10n_ar_account_reports.ar_santa_fe_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "S"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        if external_id == "l10n_ar_account_reports.ar_sifere_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id", "!=", False),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "purchase"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "customer"),
            ]
        if external_id == "l10n_ar_account_reports.ar_sircar_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "not in", ["C", "B", "T"]),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        if external_id == "l10n_ar_account_reports.ar_tucuman_iibb_return_type":
            return [
                ("tax_line_id.l10n_ar_state_id.code", "=", "T"),
                ("tax_line_id.l10n_ar_state_id.country_id.code", "=", "AR"),
                "|",
                ("tax_line_id.type_tax_use", "=", "sale"),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
            ]
        if external_id == "l10n_ar_reports.ar_tax_return_type":
            return [
                "|",
                # GRUPO A: Impuestos con código de IVA AFIP (Ventas o Compras)
                "&",
                ("tax_line_id.tax_group_id.l10n_ar_vat_afip_code", "!=", False),
                ("tax_line_id.type_tax_use", "in", ["sale", "purchase"]),
                # GRUPO B: Retenciones / Percepciones sufridas
                "&",
                "&",
                ("tax_line_id.l10n_ar_state_id", "=", False),
                ("tax_line_id.tax_group_id.l10n_ar_tribute_afip_code", "=", "06"),
                "|",
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "customer"),
                ("tax_line_id.type_tax_use", "=", "purchase"),
            ]
        if external_id == "l10n_ar_account_reports.sicore_return_type":
            return [
                ("tax_line_id.l10n_ar_tax_type", "in", ["earnings", "earnings_scale"]),
                ("tax_line_id.l10n_ar_withholding_payment_type", "=", "supplier"),
                ("tax_line_id.country_code", "=", "AR"),
            ]
        return []

    def _can_return_exist(self, company, tax_unit=False):
        """Extensión para no generar el tax return de IVA (ar_tax_return_type)
        en empresas Monotributistas o Exentas que no tienen obligación de IVA.
        """
        res = super()._can_return_exist(company, tax_unit)
        if not res:
            return False

        # Solo aplicamos la restricción al tax return de IVA nativo de Argentina
        ar_tax_return_type = self.env.ref("l10n_ar_reports.ar_tax_return_type", raise_if_not_found=False)
        if company.country_id.code == "AR" and self == ar_tax_return_type:
            # Monotributista (code=6) y Exento (code=4) no tienen obligación de IVA
            if company.l10n_ar_afip_responsibility_type_id.code in ("4", "6"):
                return False

        return res

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None):
        """
        Generate all periodic returns for Argentina (AR).

        Approach: Once we detect that a company has used a specific tax (e.g., IIBB perceptions
        for Santa Fe), we generate ALL returns for the fiscal year. This makes sense because:
        1. If you're a withholding/perception agent, you typically are for the whole year
        2. Users can see all their fiscal obligations upfront
        3. Even if a period has zero activity, they may need to file a zero declaration

        We search for activity in the current and previous fiscal year to ensure we catch
        all relevant periods, especially around year boundaries.
        """
        super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit)

        if country_code != "AR":
            return

        today = fields.Date.context_today(self)

        # Calculamos el rango de búsqueda: año fiscal actual + anterior
        # Esto garantiza que encontremos actividad incluso en cambios de año
        current_fy = main_company.compute_fiscalyear_dates(today)
        previous_fy = main_company.compute_fiscalyear_dates(current_fy["date_from"] - relativedelta(days=1))

        search_date_from = previous_fy["date_from"]
        search_date_to = current_fy["date_to"]

        ar_return_xml_ids = [
            "l10n_ar_account_reports.ar_pba_iibb_return_type",
            "l10n_ar_account_reports.ar_caba_iibb_return_type",
            "l10n_ar_account_reports.ar_mendoza_iibb_return_type",
            "l10n_ar_account_reports.ar_misiones_iibb_return_type",
            "l10n_ar_account_reports.ar_santa_fe_iibb_return_type",
            "l10n_ar_account_reports.ar_tucuman_iibb_return_type",
            "l10n_ar_account_reports.sicore_return_type",
            "l10n_ar_account_reports.ar_sifere_iibb_return_type",
            "l10n_ar_account_reports.ar_sircar_iibb_return_type",
            # Nota: ar_tax_return_type (IVA) NO está en esta lista porque tiene auto_generate=True
            # y ya se genera automáticamente en super()._generate_all_returns()
        ]

        for xml_id in ar_return_xml_ids:
            return_type = self.env.ref(xml_id, raise_if_not_found=False)
            if not return_type:
                continue

            if not return_type._can_return_exist(main_company, tax_unit):
                continue

            gi_type = main_company.l10n_ar_gross_income_type

            # Lógica de selección de reportes de IIBB según régimen
            # SIFERE y SIRCAR solo si es multilateral
            if (
                xml_id
                in [
                    "l10n_ar_account_reports.ar_sircar_iibb_return_type",
                    "l10n_ar_account_reports.ar_sifere_iibb_return_type",
                ]
                and gi_type != "multilateral"
            ):
                continue

            # Mendoza, Misiones y Santa Fe NO van si es multilateral (usan SIRCAR)
            sircar_provinces = [
                "l10n_ar_account_reports.ar_mendoza_iibb_return_type",
                "l10n_ar_account_reports.ar_misiones_iibb_return_type",
                "l10n_ar_account_reports.ar_santa_fe_iibb_return_type",
            ]
            if gi_type == "multilateral" and xml_id in sircar_provinces:
                continue

            # Caso SIFERE: se genera siempre que sea multilateral, incluso sin operaciones
            if xml_id == "l10n_ar_account_reports.ar_sifere_iibb_return_type":
                return_type._try_create_returns_for_fiscal_year(main_company, tax_unit, bypass_period_check=True)
                continue

            domain = return_type._get_l10n_ar_activity_domain()
            if not domain:
                continue

            company_ids = (
                self.env["account.return"].sudo()._get_company_ids(main_company, tax_unit, return_type.report_id)
            )

            # Buscamos actividad en el rango amplio (año fiscal anterior + actual)
            has_activity = (
                self.env["account.move.line"]
                .sudo()
                .search_count(
                    [
                        *domain,
                        ("company_id", "in", company_ids.ids),
                        ("date", ">=", search_date_from),
                        ("date", "<=", search_date_to),
                        ("parent_state", "=", "posted"),
                    ],
                    limit=1,
                )
            )

            if has_activity:
                # Generamos returns para todo el rango donde hay actividad
                # bypass_period_check=True permite crear returns incluso para períodos
                # cuyo deadline ya pasó (importante para el año fiscal anterior)
                return_type._try_create_returns_for_fiscal_year(main_company, tax_unit, bypass_period_check=True)
