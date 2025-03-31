from odoo import _, api, fields, models


class AccountAutoReconcileWizard(models.TransientModel):
    _inherit = "account.auto.reconcile.wizard"

    search_mode = fields.Selection(
        selection_add=[("all_from_partner", "All balances from one partner")],
        ondelete={"all_from_partner": "set default"},
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        compute="_compute_company_id",
        default=lambda self: self.env.company,
        store=True,
    )

    @api.depends("line_ids")
    def _compute_company_id(self):
        # Este Hack es para que podamos conciliar desde el boton del menu reconciliar
        # en un entorno multicompañia aunque estemos parados en otra compañia
        # Solo modificamos el valor por defecto si es una sola
        for rec in self:
            company = rec.line_ids.mapped("company_id")
            if len(company) == 1:
                rec.company_id = company
            else:
                rec.company_id = self.env.company

    def _auto_reconcile_all_from_partner(self):
        """Auto-reconcile with all-to-partner strategy:
        We will reconcile all amls together gruped by partner.
        :return: a recordset of reconciled amls
        """
        grouped_amls_data = self.env["account.move.line"]._read_group(
            self._get_amls_domain(),
            ["account_id", "partner_id", "currency_id", "company_id"],
            ["id:recordset"],
        )
        all_reconciled_amls = self.env["account.move.line"]
        amls_grouped_by_2 = []  # we need to group amls with right format for _reconcile_plan
        for *__, grouped_aml_ids in grouped_amls_data:
            positive_amls = grouped_aml_ids.filtered(lambda aml: aml.amount_residual_currency >= 0).sorted("date")
            negative_amls = (grouped_aml_ids - positive_amls).sorted("date")
            if positive_amls and negative_amls:
                all_reconciled_amls += positive_amls + negative_amls
                amls_grouped_by_2 += [grouped_aml_ids]
        self.env["account.move.line"]._reconcile_plan(amls_grouped_by_2)
        return all_reconciled_amls

    def auto_reconcile(self):
        """Automatically reconcile amls given wizard's parameters.
        :return: an action that opens all reconciled items and related amls (exchange diff, etc)
        """
        self.ensure_one()
        if self.search_mode == "all_from_partner":
            reconciled_amls = self._auto_reconcile_all_from_partner()
            if reconciled_amls:
                return {
                    "name": _("Automatically Reconciled Entries"),
                    "type": "ir.actions.act_window",
                    "res_model": "account.move.line",
                    "context": "{'search_default_group_by_matching': True}",
                    "view_mode": "list",
                    "domain": [("id", "in", reconciled_amls.ids)],
                }
        super().auto_reconcile()
