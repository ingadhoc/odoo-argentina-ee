##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import ast
import datetime

from dateutil.relativedelta import relativedelta
from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class AccountReport(models.Model):
    _inherit = "account.report"

    require_custom_filter = fields.Boolean(
        help="If enabled, the report will not load data unless a custom filter or partner filter is applied.",
        default=False,
    )
    filter_show_all_custom = fields.Boolean(
        string="Show All",
        readonly=False,
        store=True,
    )

    def _init_options_show_all_custom(self, options, previous_options):
        """Initialize the show_all_custom option."""
        if self.filter_show_all_custom and self.require_custom_filter:
            options["show_all_custom"] = previous_options.get("show_all_custom", False)
        else:
            options["show_all_custom"] = False

    def _init_options_filters(self, options, previous_options):
        """Override to add the require_custom_filter flag to options."""
        super()._init_options_filters(options, previous_options)
        # Only show the filter if require_custom_filter is enabled
        options["filters"]["show_all_custom"] = self.filter_show_all_custom and self.require_custom_filter

    def _get_options_domain(self, options, date_scope):
        """Override to add a dummy domain if custom filter is required and no filters are applied."""
        domain = super()._get_options_domain(options, date_scope)
        if self.require_custom_filter:
            # Si el filtro "Mostrar todo" está activo, no aplicar restricción
            if options.get("show_all_custom"):
                return domain

            custom_display_config = (
                options.get("custom_display_config", {}).get("components", {}).get("AccountReportLine")
            )
            has_partner_filter = options.get("partner_ids") and len(options.get("partner_ids", [])) > 0
            has_aml_filter = False
            has_partner_categories_filter = options.get("selected_partner_categories")

            aml_ir_filters = options.get("aml_ir_filters", [])
            if aml_ir_filters:
                has_aml_filter = any(f.get("selected") for f in aml_ir_filters)

            if (
                not has_partner_filter
                and not custom_display_config
                and not has_aml_filter
                and not has_partner_categories_filter
            ):
                domain = Domain("id", "=", False)

        return domain

    # -------------------------------------------------------------------------
    # Settlement / Closing journal entry
    # -------------------------------------------------------------------------

    allow_settlement = fields.Boolean(
        help=(
            "Esta opción habilita un botón en este reporte para liquidar todas "
            'las líneas cuya expresión tenga engine "domain".'
        )
    )
    settlement_title = fields.Char(translate=True)
    settlement_allow_unbalanced = fields.Boolean(
        help=(
            "Si se habilita esta opción, se requerirá una cuenta de contrapartida "
            "al crear el asiento de liquidación, de modo que el balance del reporte "
            "se envíe a dicha cuenta."
        )
    )

    def _init_options_buttons(self, options, previous_options):
        # OVERRIDE: llamamos al super primero para inicializar los botones base
        # (PDF, XLSX, etc.) y luego agregamos el botón de liquidación.
        super()._init_options_buttons(options, previous_options)
        if self.allow_settlement and self.settlement_title:
            options.setdefault("buttons", []).append(
                {
                    "name": "%s (BETA)" % self.settlement_title,
                    "sequence": 150,
                    "action": "action_closure_journal_entry",
                }
            )

    def action_closure_journal_entry(self, options):
        """Abre el wizard de liquidación para que el usuario elija el diario."""
        self.ensure_one()

        # En v19, options['journals'] puede incluir divisores y grupos;
        # filtramos para obtener sólo diarios reales (account.journal).
        companies = (
            self.env["account.journal"]
            .browse(
                [
                    journal["id"]
                    for journal in options.get("journals", [])
                    if journal["id"] != "divider" and journal.get("model") != "account.journal.group"
                ]
            )
            .mapped("company_id")
        )
        if len(companies) != 1:
            raise ValidationError(_("La liquidación se debe realizar filtrando por 1 y solo 1 compañía en el reporte"))

        action_name = "%s (BETA)" % self.settlement_title
        entry_ref = self.settlement_title

        new_context = {
            **self._context,
            "account_report_generation_options": options,
            "default_report_id": self.id,
            "entry_ref": entry_ref,
            "skip_invoice_sync": True,
            "default_company_id": companies.id,
        }
        view_id = self.env.ref("account_accountant_ux.view_account_tax_settlement_wizard_form").id

        return {
            "type": "ir.actions.act_window",
            "name": action_name,
            "view_mode": "form",
            "res_model": "account.tax.settlement.wizard",
            "target": "new",
            "views": [[view_id, "form"]],
            "context": new_context,
        }

    def _report_create_settlement_entry(self, journal, options, account):
        """
        Crea el asiento de liquidación/refundición.

        Itera sobre todas las expresiones del reporte cuyo engine es "domain",
        construye el dominio combinado (expresión + filtros del reporte) usando
        la API de Domain de Odoo 19, agrupa los apuntes por cuenta y genera
        las líneas de contrapartida para dejar cada cuenta en cero.
        """
        self.ensure_one()

        options = dict(options, unfold_all=True)

        report_expressions = self.env["account.report.expression"].search(
            [("report_line_id", "in", self.line_ids.ids), ("engine", "=", "domain")]
        )

        if not report_expressions:
            raise ValidationError(
                _(
                    'El reporte no tiene expresiones con engine "domain". '
                    "No es posible generar un asiento de liquidación."
                )
            )

        domains = []
        for report_expression in report_expressions:
            options_domain = self._get_options_domain(options, report_expression.date_scope)
            try:
                expression_ast = ast.literal_eval(report_expression.formula)
            except (ValueError, SyntaxError) as exc:
                expr_name = report_expression.name or str(report_expression.id)
                raise ValidationError(
                    _("La fórmula de la expresión '%(expression)s' está mal formada: %(error)s")
                    % {"expression": expr_name, "error": exc}
                ) from exc
            expression_domain = Domain(expression_ast) & options_domain
            domains.append(expression_domain)

        domain = Domain.OR(domains)

        # Agrupamos los apuntes por cuenta sumando débitos y créditos
        groups = self.env["account.move.line"].read_group(
            domain,
            ["account_id", "debit:sum", "credit:sum"],
            ["account_id"],
        )
        # Generamos las líneas del asiento como contrapartida de cada cuenta
        # (invertimos el saldo para dejarla en cero)
        currency = journal.company_id.currency_id
        lines_vals = []
        for group in groups:
            if not group.get("account_id"):
                continue
            acc_id, acc_name = group["account_id"]
            debit = group["debit"]
            credit = group["credit"]
            balance = debit - credit
            if not currency.is_zero(balance):
                lines_vals.append(
                    {
                        "name": acc_name,
                        "account_id": acc_id,
                        "debit": -balance if balance < 0.0 else 0.0,
                        "credit": balance if balance > 0.0 else 0.0,
                    }
                )
        if not lines_vals:
            raise ValidationError(_("No hay saldos para liquidar."))

        balance = sum(x["debit"] - x["credit"] for x in lines_vals)
        if not currency.is_zero(balance):
            if not self.settlement_allow_unbalanced or not account:
                raise ValidationError(
                    _(
                        "Parece que la liquidación quedaría desbalanceada. "
                        "Si desea generarla igualmente puede:\n"
                        '1. Ir a "Contabilidad / Configuración / Administración / Informes contables"\n'
                        "2. Buscar el informe correspondiente\n"
                        '3. En opciones, marcar "Settlement Allow Unbalanced"\n'
                        "4. Volver a crear el asiento seleccionando la cuenta de contrapartida solicitada"
                    )
                )
            lines_vals.append(
                {
                    "name": self.settlement_title,
                    "debit": -balance if balance < 0.0 else 0.0,
                    "credit": balance if balance >= 0.0 else 0.0,
                    "account_id": account.id,
                }
            )

        date = self._context.get("entry_date") or fields.Date.context_today(self)
        vals = {
            "journal_id": journal.id,
            "date": date,
            "ref": self.settlement_title,
            "line_ids": [fields.Command.create(line) for line in lines_vals],
        }
        move = self.env["account.move"].create(vals)
        return move

    def _init_options_date(self, options, previous_options):
        """Override to:
        1. Support 'calendar_year' filter (01/01/YYYY – 31/12/YYYY).
        2. Fix Odoo core's curr_year advancement bug for cross-calendar-year FY companies:
           after super() sets dates, re-anchor fiscal-year filters to the FY containing today.
        3. Always expose 'fiscal_year_current_string' in options['date'] so the JS dropdown
           shows the correct "YYYY - YYYY" label in every row regardless of the active filter.
        """
        date = previous_options.get("date", {})
        date_filter = date.get("filter", "custom")
        options_mode = "range" if self.filter_date_range else "single"
        today = fields.Date.context_today(self)
        # Pre-compute the actual current FY once; used for the fix and the JS label.
        fy_dates = self.env.company.compute_fiscalyear_dates(today)
        fy_base = self._get_dates_period(fy_dates["date_from"], fy_dates["date_to"], options_mode)

        if "calendar_year" in date_filter:
            period = date.get("period", 0) or 0
            year = today.year + period
            options["date"] = self._get_dates_period(
                datetime.date(year, 1, 1),
                datetime.date(year, 12, 31),
                options_mode,
                period_type="calendar_year",
            )
            options["date"]["filter"] = date_filter
            options["date"]["period"] = period
        else:
            super()._init_options_date(options, previous_options)
            # Fix: core advances cross-calendar-year FY companies to a future FY when
            # date_from.year < today.year. Re-anchor to the FY that actually contains today.
            if "year" in options.get("date", {}).get("filter", ""):
                period = options["date"].get("period", 0) or 0
                corrected = fy_base if period == 0 else self._get_shifted_dates_period(options, fy_base, period)
                options["date"].update(
                    {
                        "date_from": corrected["date_from"],
                        "date_to": corrected["date_to"],
                        "string": corrected.get("string", ""),
                    }
                )

        if "date" in options:
            options["date"]["fiscal_year_current_string"] = fy_base.get("string", "")

    def _get_dates_period(self, date_from, date_to, mode, period_type=None, options_return=False):
        """Override to handle 'calendar_year' period type and show just the year as label."""
        result = super()._get_dates_period(
            date_from, date_to, mode, period_type=period_type, options_return=options_return
        )
        if period_type == "calendar_year" and date_to:
            result["string"] = date_to.strftime("%Y")
        return result

    def _get_shifted_dates_period(self, options, period_vals, periods, return_period=False):
        """Override to handle period shifting for 'calendar_year' period type."""
        if period_vals.get("period_type") == "calendar_year":
            mode = period_vals["mode"]
            date_from = fields.Date.from_string(period_vals["date_from"])
            new_date_from = date_from + relativedelta(years=periods)
            new_date_to = datetime.date(new_date_from.year, 12, 31)
            return self._get_dates_period(new_date_from, new_date_to, mode, period_type="calendar_year")
        return super()._get_shifted_dates_period(options, period_vals, periods, return_period=return_period)

    def _expand_unfoldable_line(
        self,
        expand_function_name,
        line_dict_id,
        groupby,
        options,
        progress,
        offset,
        horizontal_split_side,
        unfold_all_batch_data=None,
    ):
        """Agregamos sufijo de compañía en reportes financieros si hay más de
        una compañía seleccionada en el método _compute_display_name de
        account.account pero necesitamos agregar por contexto el id del reporte
        porque si no lo hacemos al momento de hacer un unfold de algún rubro
        en el reporte las cuentas se muestran sin dicho sufijo. Ver ticket
        43453 para ver más info acerca de la funcionalidad que necesitamos.

        La otra mitad (el sufijo en sí) vive en
        ``account_multicompany_ux.account_account._compute_display_name``, que se
        activa justamente con este ``report_id`` de contexto. Están separados porque
        ese lado necesita ``get_company_sufix()`` de multicompañía y este lado
        necesita ``account.report`` de Enterprise: sin este módulo la clave de
        contexto nunca aparece y aquel override queda inerte.
        """
        self = self.with_context(report_id=self.id)

        return super()._expand_unfoldable_line(
            expand_function_name,
            line_dict_id,
            groupby,
            options,
            progress,
            offset,
            horizontal_split_side,
            unfold_all_batch_data,
        )
