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

            # The reports with a line component of their own never need the gate.
            custom_display_config = self.custom_handler_model_name in (
                "account.followup.report.handler",
                "account.customer.statement.report.handler",
                "account.journal.report.handler",
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

        if not (self.allow_settlement and self.settlement_title):
            return

        # ``branch_allowed`` on purpose, and it is the whole of the button-side gate.
        #
        # Without it the native one applies —"every branch in the tree is selected",
        # ``res.company._all_branches_selected``— and that is a different question than
        # the one the settlement asks: in a tree holding more than one legal entity it can
        # only be satisfied by ticking companies that do not belong in this report, and it
        # refuses every selection narrower than the tree, which is most of what
        # ``_get_settlement_company`` accepts. Two gates on one button, disagreeing, is the
        # bug this replaces.
        #
        # So the criterion is answered in exactly one place, ``action_closure_journal_entry``,
        # which knows *why* a selection is refused and says so. Enterprise offers a hook to
        # soften the native gate instead (``enable_export_buttons_for_common_vat_in_branches``,
        # "the selection is the whole group sharing a Tax ID"), and it is deliberately not
        # used: it would still gate out the per-company mode, and every other export button
        # this module and Enterprise add is already born with ``branch_allowed``, so it has
        # nothing left to allow.
        options.setdefault("buttons", []).append(
            {
                "name": "%s (BETA)" % self.settlement_title,
                "sequence": 150,
                "action": "action_closure_journal_entry",
                "branch_allowed": True,
            }
        )

    def _get_settlement_company(self, companies):
        """The company that files the settlement for ``companies``, empty if none can.

        The gate does not impose a mode. Selecting the whole legal entity and getting one
        entry that reads like the return is the suggestion, but managing it company by
        company is allowed: the accountant is the one who knows whether they need the truth
        per branch or the consolidated one. Two conditions, both about the company selector
        and nothing else:

        1. every selected company shares ``legal_entity_root_id`` — a settlement never
           mixes Tax IDs;
        2. one of the selected companies is an ancestor of all the others. That one files,
           and the entry is built there.

        The second condition is not bureaucracy. It says without ambiguity where the entry
        lands, and it rejects the one selection that cannot work: two sisters without their
        parent. ``account.account._check_company_domain`` is
        ``check_companies_domain_parent_of`` (``account/models/account_account.py``), so a
        parent reaches its branches' selections but an account living only in one branch is
        not reachable from its sister — the entry would not come out with a strange number,
        it would fail the company check. A single company, the whole entity, and a parent
        with any subset of its branches all pass for free.

        ``parent_ids`` holds the company itself and comes ordered from the root
        (``res_company._compute_parent_ids``), so "ancestor of all the others" is a
        membership test. At most one company can satisfy it.
        """
        if len(companies.legal_entity_root_id) != 1:
            return self.env["res.company"]
        return companies.filtered(lambda company: all(company in other.parent_ids for other in companies))

    def action_closure_journal_entry(self, options):
        """Abre el wizard de liquidación para que el usuario elija el diario.

        The gate is the company selector and nothing else, and it is the only one: see
        ``_get_settlement_company`` for what it accepts and why, and
        ``_init_options_buttons`` for why the button does not gate too.

        It used to demand "one and only one company", read from the companies owning the
        journals picked in the report — a different question, and a weaker one: whenever
        every selected journal happened to belong to the parent, a selection spanning
        half the entity (or another entity altogether) went through unnoticed.
        """
        self.ensure_one()

        companies = self.env.companies
        company = self._get_settlement_company(companies)
        if not company:
            entities = companies.legal_entity_root_id
            if len(entities) != 1:
                raise ValidationError(
                    _(
                        "A settlement is never filed across Tax IDs, and the selected companies belong to "
                        "%(entities)s. Select companies of a single legal entity in the company selector.",
                        entities=", ".join(entities.sudo().mapped("display_name")),
                    )
                )
            raise ValidationError(
                _(
                    "None of the selected companies is a parent of the others, so there is no company the "
                    "entry can be built in: an account that lives only in one branch cannot be used by "
                    "another one. Add %(head)s to the selection to settle them together, or select one "
                    "company at a time and settle each on its own.",
                    head=entities.sudo().display_name,
                )
            )

        action_name = "%s (BETA)" % self.settlement_title
        entry_ref = self.settlement_title

        new_context = {
            **self.env.context,
            "account_report_generation_options": options,
            "default_report_id": self.id,
            "entry_ref": entry_ref,
            "skip_invoice_sync": True,
            "default_company_id": company.id,
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
        groups = self.env["account.move.line"]._read_group(
            domain,
            ["account_id"],
            ["debit:sum", "credit:sum"],
        )
        self._check_settlement_accounts_are_reachable(
            self.env["account.account"].union(*(account for account, _debit, _credit in groups)),
            journal.company_id,
        )

        # Generamos las líneas del asiento como contrapartida de cada cuenta
        # (invertimos el saldo para dejarla en cero)
        currency = journal.company_id.currency_id
        lines_vals = []
        for account, debit, credit in groups:
            if not account:
                continue
            balance = debit - credit
            if not currency.is_zero(balance):
                lines_vals.append(
                    {
                        "name": account.display_name,
                        "account_id": account.id,
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

        date = self.env.context.get("entry_date") or fields.Date.context_today(self)
        vals = {
            "journal_id": journal.id,
            "date": date,
            "ref": self.settlement_title,
            "line_ids": [fields.Command.create(line) for line in lines_vals],
        }
        move = self.env["account.move"].create(vals)
        return move

    def _check_settlement_accounts_are_reachable(self, accounts, company):
        """Refuse before the ORM does, naming the account and what to do about it.

        ``account.account._check_company_domain`` is ``check_companies_domain_parent_of``
        (``account/models/account_account.py``): the company filing the settlement reaches
        the accounts of its ancestors and its own, but **not** an account that lives only in
        one of its branches. A branch with a result account of its own is a supported
        configuration —that is the whole point of the gate accepting a subset— so the entry
        it cannot be part of has to say so, instead of blowing up in the company consistency
        check with the account nowhere in the message.
        """
        unreachable = accounts.filtered(lambda account: not (account.company_ids & company.parent_ids))
        if not unreachable:
            return
        raise ValidationError(
            _(
                "These accounts belong only to a branch, so the entry cannot be built in %(company)s with "
                "them in it: %(accounts)s.\n"
                "Settle %(owners)s on their own —select each of them alone in the company selector— or "
                "move those accounts up to the company that files.",
                company=company.display_name,
                accounts=", ".join(unreachable.mapped("display_name")),
                owners=", ".join(unreachable.company_ids.sudo().mapped("display_name")),
            )
        )

    def _get_period_settlement_entries(self, options, company):
        """The settlement entries this report already produced for ``company`` in the period.

        A gate that accepts any subset of the entity widens the surface for settling the
        same balances twice —the whole entity one month and branch by branch the next, or
        the entity and then one of its branches again—, so the wizard says what is already
        there before creating another one. It warns and does not block: nothing here can
        tell a correction from a duplicate. The complete validation belongs to the return
        object, which is in the ROADMAP and not in this module.

        The marker is the ``ref`` the entry is created with, which is the report's own
        ``settlement_title``.
        """
        self.ensure_one()
        date = options.get("date") or {}
        if not (self.settlement_title and date.get("date_from") and date.get("date_to")):
            return self.env["account.move"]
        return self.env["account.move"].search(
            [
                ("company_id", "=", company.id),
                ("ref", "=", self.settlement_title),
                ("date", ">=", date["date_from"]),
                ("date", "<=", date["date_to"]),
            ]
        )

    def _init_options_filter_date(self, options, previous_options):
        """Add a 'Calendar Year' filter (01/01 - 31/12) next to the fiscal year one."""
        super()._init_options_filter_date(options, previous_options)
        if not self.use_fiscal_periods:
            # Without fiscal periods the native 'year' filter already is the calendar year.
            return
        range_mode = options["filter_date"]["range_mode"]
        options["filter_date"]["filters"]["calendar_year"] = {
            "key": "calendar_year",
            "label": _("Calendar Year") if range_mode else _("End of Calendar Year"),
            "months_per_period": 12,
            "start_day": 1,
            "start_month": 1,
            "sequence": 35,
            "fallback": False,
        }

    def _build_date_label(self, options, range_mode, date_from, date_to, start_day=1, start_month=1, complete=False):
        """Show just the year for a whole calendar year, as the native year filter does."""
        if (
            range_mode
            and date_from
            and date_from.year == date_to.year
            and (date_from.month, date_from.day, date_to.month, date_to.day) == (1, 1, 12, 31)
        ):
            return date_to.strftime("%Y")
        return super()._build_date_label(
            options, range_mode, date_from, date_to, start_day=start_day, start_month=start_month, complete=complete
        )

    def _expand_unfoldable_line(
        self,
        expand_function_name,
        line_dict_id,
        groupby,
        options,
        horizontal_split_side,
        unfold_all_batch_data=None,
        ignore_load_more=False,
        lines_to_skip_total_for=False,
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
            horizontal_split_side,
            unfold_all_batch_data=unfold_all_batch_data,
            ignore_load_more=ignore_load_more,
            lines_to_skip_total_for=lines_to_skip_total_for,
        )

    # -------------------------------------------------------------------------
    # Legal entity scope
    # -------------------------------------------------------------------------

    def _generate_common_warnings(self, options, warnings):
        """Suggest the companies of the legal entity that were left out of a return.

        Only on the reports that do **not** take their companies from the company selector.
        Those resolve them with ``_get_branches_with_same_vat(accessible_only=True)`` —which
        this module answers with our own legal entity criterion— and that intersects the
        entity with what is ticked, so a company of the entity left unticked silently stays
        out and the return comes out partial, with no error and no warning. The native
        warning next to this one
        (``account_reports.tax_report_warning_tax_id_selected_companies``) covers the
        opposite case only: a company that was ticked and got dropped for declaring a
        different Tax ID.

        On a report driven by the selector —the General Ledger, our Balance— the claim is
        simply false: the user picked those companies on purpose, and warning there was a
        false positive by design. Guarded with the same field the native warning uses, and
        read as "companies from the selector or not"; the ``account.tax.unit`` feature is
        not in play here and this module never uses it.

        Worded as a suggestion and not as an error, because filing part of an entity is
        allowed: what the settlement gate refuses is mixing Tax IDs, not filing branch by
        branch.
        """
        super()._generate_common_warnings(options, warnings)

        if self.filter_multi_company == "selector":
            return

        report_companies = self.env["res.company"].browse(self.get_report_company_ids(options))
        missing = self.env.company._get_branches_with_same_vat().sudo() - report_companies
        if missing:
            warnings["account_accountant_ux.warning_missing_legal_entity_companies"] = {
                "alert_type": "info",
                "args": ", ".join(missing.mapped("display_name")),
            }
