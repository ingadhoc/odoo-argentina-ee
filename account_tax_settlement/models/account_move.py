from odoo import fields, models, api
# from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # def action_export_file(self):
    #     self.ensure_one()
    #     self.journal_id.adas()
    #     return {}

    settled_line_ids = fields.One2many(
        'account.move.line',
        'tax_settlement_move_id',
        'Settled Lines',
        # atencion, si sacamos el readonly por alguna razon, volver a agregarlo
        # en la vista porque si no da error al querer guardar cambios (probar 
        # con usuario no admin pondiendo apuntes de liquidacion en cero)
        readonly=True,
        auto_join=True,
    )

    def download_tax_settlement_file(self):
        self.ensure_one()
        # para los que se liquidan desde reporte, no se encuentra el diario,
        # pero sabemos que es el diario donde se liquidaron
        return self.settled_line_ids.get_tax_settlement_file(self.journal_id)
