##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import ast

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
