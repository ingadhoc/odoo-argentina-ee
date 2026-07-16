##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.addons.account.models.company import LOCK_DATE_FIELDS
from odoo.exceptions import UserError


class AccountChangeLockDate(models.TransientModel):
    _inherit = "account.change.lock.date"

    company_id = fields.Many2one(
        "res.company", "Company", default=lambda self: self.env.company, required=True, readonly=False
    )

    @api.onchange("company_id")
    def onchange_company_id(self):
        self.sale_lock_date = self.company_id.sale_lock_date
        self.purchase_lock_date = self.company_id.purchase_lock_date
        self.fiscalyear_lock_date = self.company_id.fiscalyear_lock_date
        self.tax_lock_date = self.company_id.tax_lock_date

    def _prepare_lock_date_values(self, exception_vals_list=None):
        bypass = (
            self.env["ir.config_parameter"].sudo().get_param("account.bypass_lock_date_validation", default="False")
            == "True"
        )
        if not bypass:
            return super()._prepare_lock_date_values(exception_vals_list=exception_vals_list)
        # Bypass: devolvemos solo los lock dates que cambiaron, sin el raise del core
        # que impide bajar/quitar el hard lock date. La escritura real la deja pasar
        # res.company._validate_locks (tambien bypasseado); acá solo evitamos que el
        # wizard corte antes de llegar a esa escritura.
        return {field: self[field] for field in LOCK_DATE_FIELDS if self[field] != self.env.company[field]}

    def change_lock_date(self):
        if self.env.user.has_group("account.group_account_manager"):
            if any(
                lock_date > fields.Date.context_today(self)
                for lock_date in (
                    self.fiscalyear_lock_date,
                    self.tax_lock_date,
                )
                if lock_date
            ):
                raise UserError(_("You cannot set a lock date in the future."))
            self.company_id.sudo().write(self._prepare_lock_date_values())
        else:
            raise UserError(_("Only Billing Administrators are allowed to change lock dates!"))
        return {"type": "ir.actions.act_window_close"}
