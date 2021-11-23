from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # a este lo dejamos por ahora pero tal vez podamos evitarlo
    # igual me quiero simplificar no usando la conciliacion por ahora
    tax_settlement_move_id = fields.Many2one(
        'account.move',
        'Tax Settlement Move',
        help='Move where this tax has been settled',
        auto_join=True,
        copy=False,
    )

    def get_tax_settlement_journal(self):
        """
        Metodo para obtener el diario de liquidacion arrojando mensajes
        de error (si corresponde)
        """
        settlement_journal = self.env['account.journal']
        for rec in self:
            settlement_journal |= rec._get_tax_settlement_journal()
        if not settlement_journal:
            raise ValidationError(_(
                'No encontramos diario de liquidación para los apuntes '
                'contables: %s') % self.ids)
        elif len(settlement_journal) != 1:
            raise ValidationError(_(
                'Solo debe seleccionar líneas que se liquiden con un mismo '
                'diario, las líneas seleccionadas (ids %s) se liquidan con '
                'diarios %s') % (self.ids, settlement_journal.ids))
        return settlement_journal

    def _get_tax_settlement_journal(self):
        """
        This method return the journal that can settle this move line.
        This can be overwrited by other modules
        """
        self.ensure_one()
        return self.env['account.journal'].search([
            ('settlement_account_tag_ids', 'in', self.tax_repartition_line_id.tag_ids.ids),
            ('company_id', '=', self.company_id.id)], limit=1)

    def button_create_tax_settlement_entry(self):
        """
        Botón para el 1 a 1 que crea y postea el move
        """
        move = self.create_tax_settlement_entry()
        move.action_post()
        return move

    def create_tax_settlement_entry(self):
        """
        Funcion que crear, para los apuntes seleccionados, una liquidacion
        """
        journal = self.get_tax_settlement_journal()
        move = journal.create_tax_settlement_entry(self)
        return move

    tax_state = fields.Selection([
        ('to_settle', 'To Settle'),
        ('to_pay', 'To Pay'),
        ('paid', 'Paid'),
    ],
        'Tax State',
        compute='_compute_tax_state',
        store=True,
    )

    @api.depends(
        'tax_repartition_line_id',
        'tax_settlement_move_id.line_ids.reconciled',
    )
    def _compute_tax_state(self):
        for rec in self:
            if not rec.tax_repartition_line_id:
                state = False
            elif not rec.tax_settlement_move_id:
                state = 'to_settle'
            elif all(x.reconciled for x in rec.tax_settlement_move_id.line_ids.filtered(
                    lambda x: x.account_id.user_type_id.type in ('receivable', 'payable'))):
                state = 'paid'
            else:
                state = 'to_pay'
            rec.tax_state = state

    def action_open_tax_settlement_entry(self):
        self.ensure_one()
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.move',
            'target': 'current',
            'res_id': self.tax_settlement_move_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_pay_tax_settlement(self):
        self.ensure_one()
        open_move_line_ids = self.tax_settlement_move_id.line_ids.filtered(
            lambda r: not r.reconciled and r.account_id.internal_type in (
                'payable', 'receivable'))
        return {
            'name': _('Register Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.payment.group',
            'view_id': False,
            'target': 'current',
            'type': 'ir.actions.act_window',
            'context': {
                'to_pay_move_line_ids': open_move_line_ids.ids,
                'pop_up': True,
                'default_company_id': self.company_id.id,
                # por defecto, en pago de retenciones, no hacemos double
                # validation
                'force_simple': True,
            },
        }

# preparacion de archivos de arba, sicore, sifere, etc

    def get_tax_settlement_file(self, journal=None):
        """
        Metodo que encuentra el diario para liquidar los apuntes y devuelve
        los vals requeridos en el wizard
        """
        if not journal:
            journal = self.get_tax_settlement_journal()
        res = self.env['download_files_wizard'].action_get_files(
            journal.get_tax_settlement_files_values(self))
        return res
