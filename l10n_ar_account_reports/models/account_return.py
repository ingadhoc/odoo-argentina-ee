from collections import defaultdict

from odoo import Command, _, fields, models
from odoo.exceptions import UserError


class AccountReturn(models.Model):
    _inherit = "account.return"

    def _get_closing_report_options(self):
        """Avoid custom_return_period for sub-monthly return types.

        account_reports uses months_per_period to compute period offsets when the
        filter is ``custom_return_period``. For sub-monthly return types,
        months_per_period can be 0, which crashes the core computation
        (division by zero / invalid floor division).
        """
        if not self.type_id._is_sub_monthly_period(self.company_id):
            return super()._get_closing_report_options()

        report = self.type_id.report_id
        options = {
            "date": {
                "date_from": fields.Date.to_string(self.date_from),
                "date_to": fields.Date.to_string(self.date_to),
                "filter": "custom",
                "mode": "range",
            },
            "selected_variant_id": report.id,
            "sections_source_id": report.id,
            "tax_unit": "company_only" if not self.tax_unit_id else self.tax_unit_id.id,
            "selected_return_type_id": self.type_id.id,
        }
        company_ids = self.company_ids.ids
        return (
            report.sudo()
            .with_context(allowed_company_ids=company_ids)
            .with_company(self.company_id)
            .get_options(previous_options=options)
        )

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        l10n_ar_domain = self.type_id._get_l10n_ar_activity_domain()
        if l10n_ar_domain:
            domain += l10n_ar_domain
        return domain

    def _ensure_tax_group_configuration_for_tax_closing(self):
        """
        Skip tax group account validation for AR simple closing returns,
        since we use the partner's AP/AR accounts instead of tax group accounts.
        NOTA: esto de acá no suma tanto porque si se quiere liquidar el informde "vat" u otro igual se van a chequear
        todas las cuentas
        """
        if self.type_id.l10n_ar_is_simple_closing_return:
            return
        return super()._ensure_tax_group_configuration_for_tax_closing()

    def _get_tax_closing_payable_and_receivable_accounts(self):
        """Para simple closing returns argentinos, usamos la cuenta configurada en el return type
        o las cuentas del partner de pago. Esto permite que period_amount_to_pay y total_amount_to_pay
        se calculen correctamente basándose en las líneas del asiento de cierre.
        """
        if self.type_id.l10n_ar_is_simple_closing_return:
            # l10n_ar_account_id es company_dependent, aseguramos usar la compañía del return
            configured_account = self.type_id.with_company(self.company_id).l10n_ar_account_id
            if configured_account:
                # Si hay cuenta configurada, la usamos para ambos (payable y receivable)
                # ya que es la única cuenta donde registramos el saldo
                return configured_account, configured_account
            # Fallback: usar cuentas del partner
            partner = self.type_id.payment_partner_id
            if partner:
                return (
                    partner.with_company(self.company_id).property_account_payable_id,
                    partner.with_company(self.company_id).property_account_receivable_id,
                )
        return super()._get_tax_closing_payable_and_receivable_accounts()

    def _evaluate_total_amount_to_pay_from_tax_closing_accounts(self, payable_accounts, receivable_accounts):
        """Para simple closing returns, total_amount_to_pay = period_amount_to_pay (sin carryover).
        Esto evita que saldos históricos en las cuentas afecten el monto mostrado.
        """
        if self.type_id.l10n_ar_is_simple_closing_return:
            return self.period_amount_to_pay
        return super()._evaluate_total_amount_to_pay_from_tax_closing_accounts(payable_accounts, receivable_accounts)

    def _on_post_submission_event(self):
        """No queremos que luego de submit dispare directamente pago, prefiero que se haga click en en boton,
        mas adelante se puede implementar un wizard de submit o similar como hacen otros heredando método action_submit
        """
        if self.type_id.l10n_ar_is_simple_closing_return:
            if self.type_id.states_workflow == "generic_state_review_submit":
                return self._mark_completed()
            return
        return super()._on_post_submission_event()

    def _add_tax_group_closing_items(self, tax_group_subtotal):
        """
        EXTENDS account_reports
        For AR simple closing returns, create a simple counterpart line using the partner's AP/AR account.
        This avoids the carryover mechanism (no "Balance tax current account" lines).
        """
        if not self.type_id.l10n_ar_is_simple_closing_return:
            return super()._add_tax_group_closing_items(tax_group_subtotal)

        # Sum all tax group subtotals to get the total amount
        total = sum(tax_group_subtotal.values())
        currency = self.company_id.currency_id

        if currency.is_zero(total):
            return []

        partner = self.type_id.payment_partner_id
        if not partner:
            raise UserError(
                _(
                    "The return type '%s' has no payment partner configured. "
                    "Please set a Payment Partner on the return type.",
                    self.type_id.name,
                )
            )

        # Check if a specific account is configured on the return type
        # l10n_ar_account_id es company_dependent, aseguramos usar la compañía del return
        configured_account = self.type_id.with_company(self.company_id).l10n_ar_account_id

        line_name = _("Tax to pay") if total < 0 else _("Tax credit")
        if configured_account:
            # Use the configured account from the return type
            account = configured_account
        else:
            # Fallback: Use partner's payable account for amounts to pay, receivable for credits
            if total < 0:
                # Amount to pay (negative balance means we owe taxes)
                account = partner.with_company(self.company_id).property_account_payable_id
            else:
                # Credit in favor (positive balance means tax credit)
                account = partner.with_company(self.company_id).property_account_receivable_id

        if not account:
            raise UserError(
                _(
                    "The partner '%s' has no %s account configured for company '%s'.",
                    partner.name,
                    _("payable") if total < 0 else _("receivable"),
                    self.company_id.name,
                )
            )

        return [
            Command.create(
                {
                    "name": line_name,
                    "debit": total if total > 0 else 0,
                    "credit": abs(total) if total < 0 else 0,
                    "account_id": account.id,
                    "partner_id": partner.id,
                }
            )
        ]

    def _proceed_with_locking(self, options_to_inject=None):
        """
        For Argentinian provincial tax returns (Ingresos Brutos), we handle the locking process differently.
        We don't want to set the tax_lock_date when validating the "asiento de liquidación".
        We temporarily store the current tax_lock_date, call super(), then restore it to prevent changes.
        """
        tax_lock_dates = {
            company: company.tax_lock_date for company in self.company_ids.filtered(lambda c: c.country_id.code == "AR")
        }
        # mandamos contexto para que no se postee si no queremos
        res = super(AccountReturn, self.with_context(post_from_tax_return=True))._proceed_with_locking(
            options_to_inject=options_to_inject
        )

        # por ahora no queremos ningun informe argentino que haga lock porque, IVA, que es el principal lo estamos
        # dejando editable para que el usuario termine de acomodarlo, luego deberá hacer lock manualmente
        if self.type_id.l10n_ar_is_simple_closing_return:
            # Restore tax_lock_date to prevent it from being modified by provincial returns
            for company, original_date in tax_lock_dates.items():
                if company.tax_lock_date != original_date:
                    company.sudo().tax_lock_date = original_date

        # si no posteamos devolvemos acción
        if self.closing_move_ids.filtered(lambda m: m.state == "draft"):
            return self.closing_move_ids._get_records_action()
        return res

    def _generate_tax_closing_entries(self, options):
        """EXTENDS account_reports.

        Cuando el tipo de retorno tiene activado ``l10n_ar_single_branch_closing_entry`` y el
        return abarca una compañía padre junto con sus sucursales (branches) —a cualquier nivel de
        anidamiento— generamos un único asiento de liquidación consolidado en la compañía padre en
        lugar de uno por cada branch.

        El método nativo recorre ``company_ids`` (padre + branches) y crea un asiento por compañía.
        Acá computamos las líneas de cada compañía con el mismo helper nativo
        (``_compute_tax_closing_entry``, que aísla los montos por compañía vía ``forced_domain``),
        las concatenamos en un solo asiento de la padre y consolidamos los subtotales por grupo de
        impuesto para una única línea de contrapartida.

        Solo consolidamos cuando ``company_ids`` está formado por una compañía padre —que además
        es la compañía del return, no asumimos que el asiento siempre se cree en la padre— más
        sucursales **descendientes** suyas, sin importar la profundidad (sub-sucursales incluidas).
        Usamos ``parent_path`` para chequear pertenencia al árbol, así una jerarquía multinivel
        (padre → sucursal → sub-sucursal) consolida igual. Cualquier otro escenario multi-compañía
        (p. ej. una unidad de impuestos / tax unit con compañías no relacionadas) se delega al
        comportamiento nativo: un asiento por compañía.
        """
        self.ensure_one()

        companies = self.company_ids
        # Determinamos explícitamente la compañía padre del conjunto: la única cuyo parent no
        # pertenece al propio conjunto (la raíz de las sucursales involucradas).
        parent_company = companies.filtered(lambda c: c.parent_id not in companies)
        branches = companies - parent_company
        is_branch_consolidation = (
            self.type_id.l10n_ar_single_branch_closing_entry
            and parent_company == self.company_id
            and branches
            # ``parent_path`` ("1/5/12/") permite verificar descendencia a cualquier nivel: toda
            # branch del conjunto debe colgar del árbol de la padre (sub-sucursales incluidas).
            and all(branch.parent_path.startswith(parent_company.parent_path) for branch in branches)
        )
        if not is_branch_consolidation:
            return super()._generate_tax_closing_entries(options)

        self._ensure_tax_group_configuration_for_tax_closing()

        line_ids_vals = []
        consolidated_subtotal = defaultdict(float)
        for company in companies:
            company_lines, tax_group_subtotal = self._compute_tax_closing_entry(company, options)
            line_ids_vals += company_lines
            for key, amount in tax_group_subtotal.items():
                consolidated_subtotal[key] += amount

        line_ids_vals += self._add_tax_group_closing_items(consolidated_subtotal)

        move = self.env["account.move"].create(
            {
                "company_id": parent_company.id,
                "journal_id": parent_company._get_tax_closing_journal().id,
                "date": self.date_to,
                "closing_return_id": self.id,
                "ref": self.name,
                "line_ids": line_ids_vals,
            }
        )
        # Mantiene el comportamiento AR: action_post queda interceptado y deja el asiento en
        # borrador para los tipos de cierre argentinos (ver override en account_move.py).
        move.action_post()

    def _run_checks(self, check_codes_to_ignore):
        # if "l10n_ar_account_reports." in self.type_external_id:
        # smplificamos check de todos los reportes argentinos
        if self.company_id.country_id.code == "AR" and self.is_tax_return:
            # por ahora ignoramos todos los checks nativos para simplificar
            check_codes_to_ignore.update(
                [
                    "check_bills_attachment",
                    # "check_draft_entries",  # este nos parece útil
                    "check_match_all_bank_entries",
                    "check_tax_countries",  # odoo chequea que el country de la FP sea igual al del partner, no le vemos utlidad
                    "check_company_data",
                ]
            )
        return super()._run_checks(check_codes_to_ignore)

    def _check_draft_entries(self, code, name, message, exclude_entries=False):
        """Para liquidaciones de Argentina, filtramos los asientos en borrador para mostrar solo aquellos que
        afectan el informe que se está liquidando aprovechando el dominio de actividad ya definido.
        """
        if self.company_id.country_id.code == "AR" and self.is_tax_return:
            activity_domain = self.type_id._get_l10n_ar_activity_domain()
            if activity_domain:
                move_domain = [
                    ("state", "=", "draft"),
                    ("company_id", "in", self.company_ids.ids),
                    ("date", "<=", self.date_to),
                    ("date", ">=", self.date_from),
                    ("line_ids", "any", activity_domain),
                ]
                # en los informes argentinos evaluamos todos los tipos de asientos (por ej. retenciones son pagos)
                # if exclude_entries:
                #     move_domain.append(("move_type", "!=", "entry"))

                # El límite de 21 es el estándar de Odoo (LIMIT_CHECK_ENTRIES)
                count = self.env["account.move"].sudo().search_count(move_domain, limit=21)

                return {
                    "name": name,
                    "code": code,
                    "message": message,
                    "records_count": count,
                    "records_model": self.env["ir.model"]._get("account.move").id,
                    "action": {
                        "type": "ir.actions.act_window",
                        "name": str(name),
                        "view_mode": "list",
                        "res_model": "account.move",
                        "domain": move_domain,
                        "views": [
                            [self.env.ref("account_reports.view_draft_entries_tree").id, "list"],
                            [False, "form"],
                        ],
                    }
                    if count
                    else None,
                    "result": "anomaly" if count else "reviewed",
                }

        return super()._check_draft_entries(code, name, message, exclude_entries)

    def _get_pay_wizard(self):
        # EXTENDS account_reports
        if self.company_id.country_id.code == "AR" and self.is_tax_return and self.type_id.payment_partner_id:
            lines_to_pay = self.closing_move_ids.line_ids.filtered(
                lambda l: l.partner_id == self.type_id.payment_partner_id
                and l.account_id.account_type in ("asset_receivable", "liability_payable")
            )
            # si el saldo es a favor (balance >= 0), actualizamos estado y no abrimos wizard
            if lines_to_pay and sum(lines_to_pay.mapped("balance")) >= 0:
                self._update_payment_state()
                return
            if lines_to_pay:
                return lines_to_pay.action_register_payment()
        return super()._get_pay_wizard()

    def _update_payment_state(self):
        """Método manual para actualizar el estado basado en conciliación"""
        for record in self:
            if record.closing_move_ids:
                lines_to_pay = record.closing_move_ids.line_ids.filtered(
                    lambda l: l.partner_id == record.type_id.payment_partner_id
                    and l.account_id.account_type in ("asset_receivable", "liability_payable")
                )
                if lines_to_pay:
                    # Si el saldo es "a favor" (balance >= 0) o está conciliado, lo pasamos a pagado
                    is_paid = sum(lines_to_pay.mapped("balance")) >= 0 or all(lines_to_pay.mapped("reconciled"))
                    workflow_field = record.type_id.states_workflow
                    if is_paid and record.state != "paid":
                        record.state = "paid"
                    elif not is_paid and record.state == "paid":
                        # Si se desconcilia, volvemos al estado anterior según el workflow
                        if workflow_field == "generic_state_tax_report":
                            record.state = "submitted"
                        else:
                            record.state = "reviewed"

    def _check_suite_annual_closing(self, check_codes_to_ignore):
        checks = super()._check_suite_annual_closing(check_codes_to_ignore)

        if self.company_id.country_id.code != "AR":
            return checks

        ar_checks = []

        if "l10n_ar_cheques_a_fecha" not in check_codes_to_ignore:
            action = self.env["ir.actions.actions"]._for_xml_id(
                "l10n_latam_check_ux.action_account_check_to_date_report"
            )
            ar_checks.append(
                {
                    "name": _("Post-dated Checks"),
                    "message": _(
                        "Review and process third-party checks with deferred payment dates " "pending at period close."
                    ),
                    "code": "l10n_ar_cheques_a_fecha",
                    "action": action,
                    "result": "todo",
                }
            )

        if "l10n_ar_inflation_adjustment" not in check_codes_to_ignore:
            action = self.env["ir.actions.actions"]._for_xml_id("l10n_ar_account_reports.inflation_adjustment_action")
            ar_checks.append(
                {
                    "name": _("Inflation Adjustment Entry"),
                    "message": _("Generate the inflation adjustment journal entry for the fiscal period."),
                    "code": "l10n_ar_inflation_adjustment",
                    "action": action,
                    "result": "todo",
                }
            )

        # Insertar los pasos AR antes de "earnings_allocation"
        earnings_idx = next(
            (i for i, c in enumerate(checks) if c.get("code") == "earnings_allocation"),
            len(checks),
        )
        for offset, check in enumerate(ar_checks):
            checks.insert(earnings_idx + offset, check)

        return checks
