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
        return res

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
