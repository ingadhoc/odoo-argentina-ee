##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _validate_locks(self, values):
        # Bypass controlado por parámetro de sistema 'account.bypass_lock_date_validation'.
        # Útil para correcciones puntuales de datos (ej: desbloquear hard_lock_date).
        # Por defecto False; activar con precaución y desactivar inmediatamente después.
        bypass = (
            self.env["ir.config_parameter"].sudo().get_param("account.bypass_lock_date_validation", default="False")
        )
        if bypass == "True":
            return
        return super()._validate_locks(values)
