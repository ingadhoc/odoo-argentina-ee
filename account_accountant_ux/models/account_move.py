from odoo import models
from odoo.addons.account.models.account_move import AccountMove as AccountMoveOriginal


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_open_business_doc(self):
        """ En account_accountant odoo modifica este metodo y si tiene vinculada statement_line line te manda al statement line
        el tema es que para migraciones de 13 podes tener un asiento vinculado a statement_line y payment a la vez.
        Como ya existe un boton que permite ir a la statement_line preferimos que el boton que tiene string "pago" te
        lleve efectivamente al pago
        TODO depreciar en 17/18 ya que los datos migrados no deberian importar tanto"""
        if self.statement_line_id and self.payment_id:
            return AccountMoveOriginal.action_open_business_doc(self)
        else:
            return super().action_open_business_doc()
