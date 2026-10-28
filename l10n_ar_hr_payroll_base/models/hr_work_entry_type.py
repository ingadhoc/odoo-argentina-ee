from odoo import fields, models


class HrWorkEntryType(models.Model):
    _inherit = "hr.work.entry.type"

    l10n_ar_situation_id = fields.Many2one(
        "l10n_ar.payroll.afip.code",
        "Employment Status (AR)",
        domain=[("type", "=", "6")],
        help="Employment status of the days with this work entry, for the digital payroll book. "
        "If empty, those days keep the status of the employee history.",
    )
