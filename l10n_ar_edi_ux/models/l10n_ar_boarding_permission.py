from odoo import api, fields, models


class L10nArBoardingPermission(models.Model):
    _name = "l10n_ar.boarding_permission"
    _description = "Boarding Permission"

    number = fields.Char(string="Boarding Permission Number", required=True, size=16)
    dst_country = fields.Many2one(
        "res.country", string="Destination Country", help="Destination country of the goods", required=True
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    _permiso_embarque_unique = models.Constraint(
        "UNIQUE(number, dst_country, company_id)",
        "Boarding permission already exists.",
    )

    _rec_names_search = ["number", "dst_country"]

    @api.depends("number", "dst_country")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s - %s" % (rec.number, rec.dst_country.display_name)
