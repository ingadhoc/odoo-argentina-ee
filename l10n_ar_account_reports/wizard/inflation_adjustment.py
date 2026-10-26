##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from dateutil.relativedelta import relativedelta
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, formatLang


class InflationAdjustment(models.TransientModel):
    _name = "inflation.adjustment"
    _description = "Inflation adjustment"

    date_from = fields.Date(
        required=True,
    )
    date_to = fields.Date(
        required=True,
    )
    journal_id = fields.Many2one(
        "account.journal", domain=[("type", "=", "general")], required=True, check_company=True
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        help="Company the entry is built in: the one of the selected companies that is a parent of the others.",
    )
    company_ids = fields.Many2many(
        "res.company",
        string="Companies",
        readonly=True,
        help="Companies whose journal items are adjusted: the ones selected in the company selector.",
    )
    missing_companies_warning = fields.Char(
        readonly=True,
    )
    account_id = fields.Many2one("account.account", domain=[("active", "=", True)], required=True, check_company=True)
    start_index = fields.Float(
        compute="_compute_index",
    )
    end_index = fields.Float(
        compute="_compute_index",
    )
    open_cloure_entry = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Has Closing/Opening Entries?",
        default="no",
        help="If you have made the closing/opening entries, please indicate them"
        " so they can be excluded from the calculation.",
    )
    closure_move_ids = fields.Many2many(
        "account.move",
        "inflation_adjustment_closure_move_rel",
        string="Closing Entries",
        help="One per selected company that has its own closing entry.",
    )
    open_move_ids = fields.Many2many(
        "account.move",
        "inflation_adjustment_open_move_rel",
        string="Opening Entries",
        help="One per selected company that has its own opening entry.",
    )
    missing_entries_warning = fields.Char(
        compute="_compute_missing_entries_warning",
    )

    def get_account_id(self, line):
        return line.get("account_id")[0]

    @api.model
    def default_get(self, field_list):
        res = super(InflationAdjustment, self).default_get(field_list)
        today = fields.Datetime.now()
        companies = self.env.companies
        head = companies._get_filing_company()
        # Without a head the wizard still opens; _check_companies refuses it at confirm.
        company = head or self.env.company
        res["company_id"] = company.id
        res["company_ids"] = [Command.set(companies.ids)]
        # Only when the selection can be adjusted: otherwise the gate refuses it at confirm, and says why.
        if head:
            missing = companies._get_legal_entity_companies_left_out(selectable_only=True)
            if missing:
                res["missing_companies_warning"] = _(
                    "These companies of the same legal entity are not selected, so their journal items will not "
                    "be adjusted: %(companies)s. Select them in the company selector if you meant to adjust the "
                    "whole entity.",
                    companies=", ".join(missing.mapped("display_name")),
                )
        company_fiscalyear_dates = company.compute_fiscalyear_dates(today - relativedelta(year=today.year - 1))
        # Filter out keys that are not fields of this model (e.g., 'record')
        for key, value in company_fiscalyear_dates.items():
            if key in self._fields:
                res[key] = value
        return res

    @api.depends("open_cloure_entry", "company_ids", "company_id", "closure_move_ids", "open_move_ids")
    def _compute_missing_entries_warning(self):
        """Name the selected companies with no closing or opening entry chosen.

        A suggestion, not a check: whether a company closed the year on its own cannot be
        told from its entries. Only once an entry of a branch is chosen, which says the
        entity closes branch by branch; when it closes only in its head, the branches have
        none and there is nothing to warn about.
        """
        for rec in self:
            rec.missing_entries_warning = False
            if rec.open_cloure_entry != "yes":
                continue
            # Sudo: the res.company rule only lets the user read the companies ticked right now.
            entries = (rec.closure_move_ids | rec.open_move_ids).sudo()
            if not (entries.company_id - rec.company_id.sudo()):
                continue
            closures = rec.closure_move_ids.sudo().company_id
            openings = rec.open_move_ids.sudo().company_id
            without = rec.sudo().company_ids.filtered(
                lambda company: company not in closures or company not in openings
            )
            if without:
                rec.missing_entries_warning = _(
                    "No closing or opening entry was chosen for %(companies)s. If they closed the year on their "
                    "own, add those entries too: otherwise they are adjusted as movements of the period.",
                    companies=", ".join(without.mapped("display_name")),
                )

    @api.depends("date_from", "date_to")
    def _compute_index(self):
        """Update index when dates has been updated"""
        index_obj = self.env["inflation.adjustment.index"]
        start_index = index_obj.find(self.date_from)
        end_index = index_obj.find(self.date_to)
        self.start_index = start_index.value
        self.end_index = end_index.value

    def get_periods(self):
        """return a list of periods where the inflation adjustment will be
        apply.

        If not found index in any of the months in the selected period then
        a UserError exception will be thrown

        :return: [{
          'date_from': <first_date_month>, (for first period date_from date)
          'date_to': <last_date_month>,
          'factor': end_index / <month_index>,
          'index': recordset('inflation.adjustment.index')}, ...]
        """
        if self:
            self.ensure_one()
            start_date = self.date_from
            end_date = self.date_to
            end_index = self.end_index
        else:
            end_index = self.env["inflation.adjustment.index"].find(end_date).value

        if not start_date or not end_date:
            raise UserError(_("Please specify the start and end date range"))

        res = []

        indexes = self.env["inflation.adjustment.index"].search([("date", ">=", start_date), ("date", "<=", end_date)])

        while start_date < end_date:
            date_to = start_date + relativedelta(months=1, days=-1)
            if date_to > end_date:
                date_to = end_date

            index = indexes.filtered(lambda x: x.date >= start_date and x.date <= date_to)
            if not index:
                message = _(
                    "The inflation adjustment entry cannot be generated because the adjustment index for period %(month)s %(year)s is missing"
                ) % {
                    "month": start_date.strftime("%B"),
                    "year": start_date.year,
                }
                raise UserError(message)

            res.append(
                {
                    "date_from": start_date,
                    "date_to": date_to,
                    "index": index,
                    "factor": (end_index / index.value) - 1.0,
                }
            )
            start_date += relativedelta(months=1, day=1)
        return res

    def _check_companies(self):
        self.ensure_one()
        # Sudo: the res.company rule only lets the user read the companies ticked right now.
        companies = self.sudo().company_ids
        if not companies:
            raise UserError(_("Select the companies to adjust in the company selector."))
        entities = companies.legal_entity_root_id
        if len(entities) != 1:
            raise UserError(
                _(
                    "An inflation adjustment is never done across Tax IDs, and the selected companies belong to "
                    "%(entities)s. Select companies of a single legal entity in the company selector.",
                    entities=", ".join(entities.sudo().mapped("display_name")),
                )
            )
        head = companies._get_filing_company()
        if head and head != self.company_id.sudo():
            raise UserError(
                _(
                    "The entry of the selected companies is built in %(head)s, not in %(company)s.",
                    head=head.display_name,
                    company=self.company_id.sudo().display_name,
                )
            )
        if not head:
            raise UserError(
                _(
                    "None of the selected companies is a parent of the others, so there is no company the "
                    "entry can be built in. Add %(head)s to the selection to adjust them together, or select one "
                    "company at a time and adjust each on its own.",
                    head=entities.sudo().display_name,
                )
            )

    def _check_accounts_are_reachable(self, accounts):
        """Name the accounts the entry cannot use before the company check of the ORM does."""
        company = self.company_id.sudo()
        accounts = accounts.sudo()
        unreachable = accounts.filtered(lambda account: not (account.company_ids & company.parent_ids))
        if unreachable:
            raise UserError(
                _(
                    "These accounts belong only to a branch, so the entry cannot be built in %(company)s with "
                    "them in it: %(accounts)s.\n"
                    "Adjust %(owners)s on their own —select each of them alone in the company selector— or "
                    "move those accounts up to the company that files.",
                    company=company.display_name,
                    accounts=", ".join(unreachable.mapped("display_name")),
                    owners=", ".join((unreachable.company_ids & self.sudo().company_ids).mapped("display_name")),
                )
            )

    def get_move_line_domain(self):
        self.ensure_one()
        res = [
            ("account_id.is_monetary", "=", False),
            ("company_id", "in", self.sudo().company_ids.ids),
            ("move_id.state", "=", "posted"),
        ]
        excluded = self.open_move_ids | self.closure_move_ids
        # Answering "No" hides the fields but keeps their values.
        if self.open_cloure_entry == "yes" and excluded:
            res += [("move_id", "not in", excluded.ids)]
        return res

    def confirm(self):
        """Search all the related account.move.line and will create the
        related inflation adjustment journal entry for the specification.
        """

        def FormatAmount(amount):
            return formatLang(self.env, amount, currency_obj=self.company_id.currency_id)

        self.ensure_one()
        self._check_companies()
        account_move_line = self.env["account.move.line"]
        adjustment_total = {"debit": 0.0, "credit": 0.0}
        lines = []

        # Generate account.move.line adjustment for start of the period
        domain = self.get_move_line_domain()
        domain += [("account_id.include_initial_balance", "=", True), ("date", "<", self.date_from)]
        init_data = account_move_line.read_group(
            domain,
            ["account_id", "balance"],
            ["account_id"],
        )
        date_to = self.date_to
        before_date_from = self.date_from + relativedelta(months=-1)
        before_index = self.env["inflation.adjustment.index"].find(before_date_from)
        if not before_index:
            raise UserError(
                _(
                    "No inflation adjustment index was found for the previous date (%s). "
                    "Please configure the corresponding index."
                )
                % format_date(self.env, before_date_from)
            )

        initial_factor = (self.end_index / before_index.value) - 1.0
        for line in init_data:
            adjustment = line.get("balance") * initial_factor
            if self.company_id.currency_id.is_zero(adjustment):
                continue
            else:
                adjustment = self.company_id.currency_id.round(adjustment)
            lines.append(
                {
                    "account_id": self.get_account_id(line),
                    "name": _("Inflation adjustment opening balances (%s * %.2f%%)")
                    % (FormatAmount(line.get("balance")), initial_factor * 100.0),
                    "date_maturity": before_date_from,
                    "debit" if adjustment > 0 else "credit": abs(adjustment),
                }
            )
            adjustment_total["debit" if adjustment > 0 else "credit"] += abs(adjustment)

        # Get period month list
        periods = self.get_periods()

        for period in periods:
            # search account.move.lines
            domain = self.get_move_line_domain()
            domain += [("date", ">=", period.get("date_from")), ("date", "<=", period.get("date_to"))]
            data = account_move_line.read_group(domain, ["account_id", "balance"], ["account_id", "date"])
            date_from = period.get("date_from")
            for line in data:
                adjustment = line.get("balance") * period.get("factor")
                if self.company_id.currency_id.is_zero(adjustment):
                    continue
                else:
                    adjustment = self.company_id.currency_id.round(adjustment)
                lines.append(
                    {
                        "account_id": self.get_account_id(line),
                        "name": _("Inflation adjustment %s (%s * %.2f%%)")
                        % (
                            format_date(self.env, date_from, date_format="MM/Y"),
                            FormatAmount(line.get("balance")),
                            period.get("factor") * 100.0,
                        ),
                        "date_maturity": period.get("date_from"),
                        "debit" if adjustment > 0 else "credit": abs(adjustment),
                    }
                )
                adjustment_total["debit" if adjustment > 0 else "credit"] += abs(adjustment)

        if not lines:
            raise UserError(_("No journal entries to adjust were found for the selected period."))
        self._check_accounts_are_reachable(
            self.account_id | self.env["account.account"].browse({line["account_id"] for line in lines})
        )

        # Generate total amount adjustment line
        adj_diff = adjustment_total.get("debit", 0.0) - adjustment_total.get("credit", 0.0)
        lines.append(
            {
                "account_id": self.account_id.id,
                "name": _("Global Inflation Adjustment [%s] / [%s]") % (self.date_from, self.date_to),
                "debit" if adj_diff < 0 else "credit": abs(adj_diff),
                "date_maturity": self.date_to,
            }
        )

        # Generate account.move
        move = (
            self.env["account.move"]
            .with_context(skip_invoice_sync=True)
            .create(
                {
                    "journal_id": self.journal_id.id,
                    # Explicit: a branch may book with its parent's journal.
                    "company_id": self.company_id.id,
                    "date": self.date_to,
                    "ref": _("Inflation Adjustment %s") % (date_to.year),
                    "line_ids": [(0, 0, line_data) for line_data in lines],
                }
            )
        )
        return move._get_access_action()
