##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountReconcileWizard(models.TransientModel):
    _inherit = "account.reconcile.wizard"

    multiple_partners = fields.Boolean(compute="_compute_multiple_partners")

    @api.depends("move_line_ids")
    def _compute_reco_wizard_data(self):
        super()._compute_reco_wizard_data()
        for wizard in self:
            if (
                not wizard.company_id.reconcile_on_company_currency
                or not wizard.reco_currency_id
                or wizard.reco_currency_id == wizard.company_currency_id
            ):
                continue
            # Con reconcile_on_company_currency la conciliación es íntegramente
            # en moneda de compañía. El wizard nativo elige USD como reco_currency
            # cuando hay una sola moneda foránea y convierte el residual ARS→USD→ARS
            # usando cotizaciones diferentes, introduciendo error de redondeo
            # (ej. 510 ARS → 0,36 USD × 1400 = 504 ARS). Forzamos moneda de
            # compañía y calculamos el importe desde el balance neto de los apuntes,
            # que siempre coincide con el write-off necesario.
            company_currency = wizard.company_currency_id
            wizard.reco_currency_id = company_currency
            net = company_currency.round(sum(aml.amount_residual for aml in wizard.move_line_ids._origin))
            wizard.amount = net
            wizard.amount_currency = net

    @api.depends("move_line_ids.partner_id")
    @api.depends_context("active_ids")
    def _compute_multiple_partners(self):
        for wizard in self:
            wizard.multiple_partners = False
            active_ids = self.env.context.get("active_ids")
            if active_ids:
                partner_ids = self.env["account.move.line"].browse(active_ids).mapped("move_id.partner_id")
                if len(set(partner_ids)) > 1:
                    wizard.multiple_partners = True

    def reconcile(self):
        """Bloquea la conciliación entre compañías distintas cuando la compañía lo pide.

        El flag ``block_intercompany_conciliation`` se define en este mismo módulo: el
        único lugar donde se aplica es este wizard, que es de Enterprise
        (``account_accountant``), así que la opción y su enforcement viven juntos y
        ``account_multicompany_ux`` no necesita depender de Enterprise para ofrecerla.
        """
        for wizard in self:
            companies = wizard.move_line_ids.mapped("company_id")
            if len(companies) > 1 and companies.filtered(lambda c: c.child_ids and c.block_intercompany_conciliation):
                raise UserError(
                    "Cannot reconcile journal items from different companies. "
                    "Please verify that the 'Block inter-company reconciliation' option "
                    "is not enabled in the settings of the companies involved."
                )
        return super().reconcile()
