from odoo import models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """ Si la factura es rectificativa y tiene percepciones de misiones la misma tiene que tener el mismo importe que la factura original y fecha igual o posterior a la de la factura original """
        for amount in self.amount_by_group:
            if amount[0] == 'Percepción IIBB Misiones' and self.reversed_entry_id and self.amount_total != self.reversed_entry_id.amount_total:
                raise ValidationError("Si está haciendo una factura rectificativa con percepciones de misiones, la misma debe hacerse sobre el importe total de la factura original")
        return super().action_post()
