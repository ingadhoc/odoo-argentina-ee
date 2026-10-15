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
        for field in LOCK_DATE_FIELDS:
            self[field] = self.company_id[field]

    # The enterprise wizard compares, validates and writes the lock dates against env.company. Since the company
    # can be picked in the wizard (e.g. a branch), we run that logic on the selected company instead.

    def _get_changes_needing_exception(self):
        return super(AccountChangeLockDate, self.with_company(self.company_id))._get_changes_needing_exception()

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
        if self.env.user.has_group("account.group_account_manager") and any(
            lock_date > fields.Date.context_today(self)
            for lock_date in (self.fiscalyear_lock_date, self.tax_lock_date)
            if lock_date
        ):
            raise UserError(_("You cannot set a lock date in the future."))
        return super(AccountChangeLockDate, self.with_company(self.company_id)).change_lock_date()
