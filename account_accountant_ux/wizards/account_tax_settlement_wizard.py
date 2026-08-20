##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models


class AccountTaxSettlementWizard(models.TransientModel):
    """
    Wizard para liquidar impuestos desde reportes contables.

    Permite al usuario seleccionar el diario en el que se registrará el asiento
    de liquidación y, opcionalmente, una cuenta de contrapartida cuando el
    reporte tiene habilitada la opción ``settlement_allow_unbalanced``.
    """

    _name = "account.tax.settlement.wizard"
    _description = "Wizard para generar liquidaciones de impuestos desde reportes"

    date = fields.Date(
        string="Fecha del asiento",
        required=True,
        default=fields.Date.context_today,
    )
    settlement_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario",
        required=True,
        check_company=True,
        domain=[("type", "=", "general")],
    )
    report_id = fields.Many2one(
        comodel_name="account.report",
        string="Reporte",
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        readonly=True,
    )
    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de contrapartida",
        check_company=True,
        domain=[("active", "=", True)],
    )
    report_settlement_allow_unbalanced = fields.Boolean(
        related="report_id.settlement_allow_unbalanced",
        string="Permite desbalance",
    )
    already_settled_warning = fields.Char(
        string="Ya liquidado",
        readonly=True,
        help="Advertencia si la compañía que liquida ya tiene un asiento de liquidación de este "
        "reporte en el período. No bloquea: puede ser una corrección.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Precargamos el diario filtrando por la compañía del contexto
        company_id = self._context.get("default_company_id")
        if company_id and "settlement_journal_id" in fields_list:
            journal = self.env["account.journal"].search(
                [("company_id", "=", company_id), ("type", "=", "general")],
                limit=1,
            )
            if journal:
                res["settlement_journal_id"] = journal.id
        if company_id and "already_settled_warning" in fields_list:
            res["already_settled_warning"] = self._get_already_settled_warning(company_id)
        return res

    @api.model
    def _get_already_settled_warning(self, company_id):
        """Say it if this company already settled this report for this period.

        The settlement gate accepts any subset of the legal entity, so the same balances can
        be settled twice —the whole entity one month and branch by branch the next, or the
        entity and then one of its branches again— and nothing downstream notices. It is not
        a new risk (the gate used to be "one and only one company", and repeating was just as
        possible), so this is the cheap cover for it and not a validation: a second entry may
        well be a correction. The real one arrives with the return object, in the ROADMAP.
        """
        report = self.env["account.report"].browse(self._context.get("default_report_id"))
        if not report:
            return False
        options = self._context.get("account_report_generation_options") or {}
        company = self.env["res.company"].browse(company_id)
        existing = report._get_period_settlement_entries(options, company)
        if not existing:
            return False
        return _(
            "%(company)s already has a settlement entry of this report for this period: %(entries)s. "
            "Creating another one settles the same balances twice.",
            company=company.display_name,
            entries=", ".join(existing.mapped("display_name")),
        )

    def confirm(self):
        """Crea el asiento de liquidación y redirige al usuario al asiento creado."""
        self.ensure_one()
        options = self._context.get("account_report_generation_options", {})
        move = self.report_id.with_context(
            skip_invoice_sync=True,
            entry_date=self.date,
        )._report_create_settlement_entry(
            journal=self.settlement_journal_id,
            options=options,
            account=self.account_id,
        )
        return {
            "name": _("Asiento de liquidación"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "account.move",
            "res_id": move.id,
            "target": "current",
        }
