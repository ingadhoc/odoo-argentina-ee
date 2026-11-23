from odoo import api, fields, models


class L10nArPayrollAfipCode(models.Model):
    _name = "l10n_ar.payroll.afip.code"
    _description = "ARCA code for the digital payroll book"
    _order = "type, code"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    type = fields.Selection(
        [
            ("1", "Condition"),
            ("2", "Activity"),
            ("3", "Hiring Modality"),
            ("4", "Casualty"),
            ("5", "Zone"),
            ("6", "Employment Status"),
            ("7", "Health Insurance"),
        ],
        required=True,
    )
    active = fields.Boolean(default=True)

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code} - {rec.name}"
