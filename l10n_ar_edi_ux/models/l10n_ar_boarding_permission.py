from odoo import fields, models, api


class L10nArBoardingPermission(models.Model):
    _name = "l10n_ar.boarding_permission"
    _description = 'Boarding Permission'

    number = fields.Char(string="Permiso de embarque", required=True, size=16)
    dst_country = fields.Many2one('res.country', string="País de destino", help="País de destino de la mercadería", required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    _sql_constraints = [
        ('permiso_embarque_unique', 'UNIQUE(number, dst_country, company_id)', 'Error! El permiso de embarque ya existe.'),
    ]

    def name_get(self):
        result = []
        for rec in self:
            result.append(
                (rec.id, "%s - %s" % (rec.number, rec.dst_country.display_name)))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('number', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('dst_country', operator, name)] + args, limit=limit)
        return recs.name_get()
