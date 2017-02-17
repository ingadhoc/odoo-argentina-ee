# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api
# from openerp.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.multi
    def write(self, vals):
        """
        El javascript para agregar anotacion escribe sobre move line pasando
        el id de un debt line. Lo cambiamos para escribir los debt lines
        que corresponde. Deberiamos cambiar el javascript y el metodo write
        de debt line, seria mas prolijo
        """

        from_move_line = self._context.get('from_move_line')
        # si solo vienen internal note y expeted date y si no viene la clave
        # que mandamos, es porque se viene del pop up
        if (
                not from_move_line and 'expected_pay_date' in vals and
                'internal_note' in vals and len(vals) == 2):
            debt_lines = self.env['account.debt.line'].browse(self.ids)
            return debt_lines.move_line_ids.with_context(
                from_move_line=True).write({
                    'expected_pay_date': vals.get('expected_pay_date'),
                    'internal_note': vals.get('internal_note'),
                })
        return super(AccountMoveLine, self).write(vals)

    @api.multi
    def write_blocked(self, blocked):
        """
        We inherit original to block move lines by receiving id from debt line
        """
        debt_lines = self.env['account.debt.line'].browse(self.ids)
        return debt_lines.move_line_ids.with_context(
            check_move_validity=False).write({'blocked': blocked})
