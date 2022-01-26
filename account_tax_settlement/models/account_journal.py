from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)
# from odoo.tools.misc import formatLang
# from datetime import datetime
# from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
# import re


class AccountJournal(models.Model):
    """
    Hy basicamente dos maneras en las que creamos asientos de liquidación:
    * A través del repotes: para eso debe haber un reporte vinculado y, además,
    el reporte debe tener seteados los campos relativos a liquidación
    * A través de tags: si definimos tags, se buscan impuestos pendientes de
    liquidar que tengan esos tags. Esta segunda opción es requerida si queremos
    permitir liquidación línea a línea

    Se pueden usar ambas opciones pero la primera tiene más prioridad (por lo
    cual desde el botón new settlement se elige la primera si está disponible)
    """
    _inherit = 'account.journal'

    tax_settlement = fields.Selection([
        ('yes', 'Yes'),
        ('allow_per_line', 'Yes, allow per line'),
    ],
    )
    # lo re incorporamos ya
    # quincenal de ganancias
    # TODO analizar si renombrar si es que solo lo usamos para el tema de
    # archivos
    settlement_tax = fields.Selection(
        [],
        string='Impuesto de liquidación',
        help='Si elije un impuesto se puede agregar alguna funcionalidad, como'
        ' por ej. descargar archivos txt'
    )
    # viejo, no estaríamos usando más qweb
    # settlement_file_template = fields.Many2one(
    #     'ir.ui.view',
    #     domain=[('type', '=', 'qweb')],
    # )
    settlement_partner_id = fields.Many2one(
        'res.partner',
        'Partner de liquidación',
    )
    settlement_financial_report_id = fields.Many2one(
        'account.financial.html.report',
        'Informe de liquidación',
    )
    # lo hacemos con etiquetas ya que se puede resolver con datos en plan
    # de cuentas sin incorporar lógica
    # TODO, por ahora son solo con tags de impuestos pero podrimoas dejar
    # que sea tmb con tags de cuentas, analizar...
    settlement_account_tag_ids = fields.Many2many(
        'account.account.tag',
        'account_journal_account_tag',
        auto_join=True,
        string='Etiquetas para liquidación',
        help='Se pueden elegir etiquetas de impuestos y/o cuentas:\n'
        '* Para las de impuestos se van a liquidar los apuntes contables de '
        'impuestos con esa etiqueta\n'
        '* Para las de cuentas contables solamente se van crear líneas en cero'
        ' en el asiento de liquidación para cada cuenta que tengan esa '
        'etiqueta',
        # TODO analizar
        # al final dejamos elegir tags de cuentas o taxes. Los de cuentas,
        # por ahora, son solo para llevar esa cuenta contable en una línea
        # en cero pero podemos llegar a usarlo para que lleve saldo
        # o algo así
        # domain=[('applicability', '=', 'taxes')],
        # # context={'default_applicability': 'taxes'},
        # string='Etiquetas de impuestos liquidados',
        # help="Taxes with this tags are going to be settled by this journal"
    )
    # changing domain for default_account_id is not working, we create this related field just to change domain
    settlement_account_id = fields.Many2one(
        related='default_account_id',
        string="Cuenta de contrapartida",
        readonly=False,
        domain="[('deprecated', '=', False), ('user_type_id.type', 'in', ('receivable', 'payable')), ('company_id', '=', company_id)]")

    @api.constrains('tax_settlement', 'type')
    def check_tax_settlement(self):
        for rec in self:
            if rec.tax_settlement:
                if rec.type != 'general':
                    raise ValidationError(_(
                        'Solo se puede usar "Impuesto de liquidación" en '
                        'diarios del tipo "Miscelánea"'))
                if not rec.settlement_partner_id:
                    raise ValidationError(_(
                        'Si usa "Impuesto de liquidación" debe setear un '
                        '"Partner de liquidación"'))

    def action_create_payment(self):
        partner = self.settlement_partner_id
        if not partner:
            raise ValidationError(_(
                'You can only create payment if journal has settlement partner'
                ' configured!'))
        return {
            'name': _('Register Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.payment.group',
            'view_id': False,
            'target': 'current',
            'type': 'ir.actions.act_window',
            'context': {
                'default_partner_id': partner.id,
                'default_partner_type': 'supplier',
                # 'to_pay_move_line_ids': open_move_line_ids.ids,
                # 'pop_up': True,
                # 'default_company_id': self.company_id.id,
            },
        }

####################################
# Métodos compartidos de liquidación
####################################

    # este metodo funciona pero no lo usamos porque por ahora estamos haciendo
    # que se use seleccioando varias líneas desde lineas a liquidar
    # lo dejamos por si sirve para algun otro caso de uso
    # def action_create_tax_settlement_entry(self):
    #     # hacemos que sea obligatorio una fecha hasta, si no viene, llamamos
    #     # al wizard para definir fechas y luego recien continuamos
    #     if not self._context.get('to_date'):
    #         return self.env['get_dates_wizard'].open_wizard(
    #             'action_create_tax_settlement_entry')

    #     if self.settlement_financial_report_id:
    #         unsettled_lines = self._get_tax_settlement_move_lines_by_report()
    #     else:
    #         unsettled_lines = self._get_tax_settlement_move_lines_by_tags()
    #     if not unsettled_lines:
    #         raise ValidationError(_(
    #             'No lines funded to be settled with this conditions'))
    #     move = self.create_tax_settlement_entry(unsettled_lines)
    #     return {
    #         'name': _('Journal Entries'),
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_model': 'account.move',
    #         'target': 'current',
    #         'res_id': move.id,
    #         'type': 'ir.actions.act_window',
    #     }

    def create_tax_settlement_entry(self, move_lines):
        """
        Función que recibe move lines y crea una liquidación en este diario
        agrupando por cuenta contable. (se usa desde apuntes contables)
        Devuelve un browse del move creado
        """
        self.ensure_one()
        draft_lines = move_lines.filtered(lambda x: x.move_id.state == 'draft')
        if draft_lines:
            raise ValidationError(_(
                'A seleccionado apuntes contables de asientos en borrador. '
                'Solo puede liquidar apuntes de asientos publicados. Apuntes: %s') % draft_lines.ids)
        if not self.tax_settlement:
            raise ValidationError(_(
                'Settlement only allowed on journals with Tax Settlement '
                'enable'))

        if move_lines.filtered('tax_settlement_move_id'):
            raise ValidationError(_(
                'You can not settle lines that has already been settled!\n'
                '* Lines ids: %s') % (
                move_lines.filtered('tax_settlement_move_id').ids))
        # if not self.tax_id:
        #     raise ValidationError(_(
        #         'Settlement only allowed for journal items with tax code'))

        # en realidad no, porque saldos a favor no requiere que sea a pagar..
        # check account type so that we can create a debt
        # if account.type != 'payable':
        #     raise ValidationError(_(
        #         'La cuenta de contrapartida en diarios de liquidación debe '
        #         'ser a pagar. Account id %s' % account.id))

        # TODO ver como implementamos el anterior!
        lines_vals = self._get_tax_settlement_entry_lines_vals(
            [('id', 'in', move_lines.ids)])
        vals = self._get_tax_settlement_entry_vals(lines_vals)
        move = self.env['account.move'].create(vals)
        move_lines.write({'tax_settlement_move_id': move.id})
        return move

    def _get_tax_settlement_entry_lines_vals(self, domain=None):
        # TODO agregar la parte dinamica
        grouped_move_lines = self.env['account.move.line'].read_group(
            domain, ['account_id', 'balance', 'amount_currency'], ['account_id'])

        new_move_lines = []
        balance = 0.0
        # hacemos esto para verificar que todos sean de la misma moneda
        company_currency = self.company_id.currency_id
        is_zero = self.company_id.currency_id.is_zero
        for group in grouped_move_lines:
            group_balance = company_currency.round(group['balance'])
            if is_zero(group_balance):
                continue
            balance += group_balance
            # amount_currency += group_amount_currency
            # balane es debito menos credito, si es positivo entonces hay mas
            # debito y tenemos que mandar a credito
            new_vals_line = {
                'name': self.name,
                'debit': group_balance < 0.0 and -group_balance,
                'credit': group_balance >= 0.0 and group_balance,
                'account_id': group['account_id'][0],
            }
            # if we find an account with secondary currency, we consider that
            #  the new aml must have currency and amount currency
            currency = group['account_id'][0] and self.env['account.account'].browse(group['account_id'][0]).currency_id
            if currency:
                if new_vals_line['debit'] > 0.0:
                    amount_currency = group['amount_currency'] < 0.0 and\
                        -group['amount_currency'] or group['amount_currency']
                else:
                    amount_currency = group['amount_currency'] > 0.0 and\
                        -group['amount_currency'] or group['amount_currency']
                new_vals_line.update({
                    'currency_id': currency.id,
                    'amount_currency': amount_currency
                })
            new_move_lines.append(new_vals_line)

        # agregamos la info para que se creen lineas para cada cuenta
        # etiquetada (estas lineas se llevan en cero)
        domain = [('company_id', '='), ('deprecated', '=', False)]
        account_tags = self.settlement_account_tag_ids.filtered(
            lambda x: x.applicability == 'accounts')
        if account_tags:
            domain.append(('tag_ids', 'in', account_tags.ids))
            for account in self.env['account.account'].search([
                    ('company_id', '=', self.company_id.id),
                    ('deprecated', '=', False),
                    ('tag_ids', 'in', account_tags.ids)]):
                new_move_lines.append({
                    'name': self.name,
                    'debit': 0.0,
                    'credit': 0.0,
                    'account_id': account.id,
                })
        return new_move_lines

    def _get_tax_settlement_entry_vals(self, lines_vals):
        """
        Esta funcion recibe las values de las lineas de liquidación (lineas
        que van a liquidar lo que se haya solicitado liquidar) y genera
        los vals para generar el asiento.
        Por ahora sacamos la liquidación de la parte en otra moneda ya que
        ensucia más que ayudar
        """
        self.ensure_one()

        balance = sum(map(lambda x: x['debit'] - x['credit'], lines_vals))

        # si el balance es distinto de cero agregamos cuenta contable
        if not self.company_id.currency_id.is_zero(balance):
            # check account payable
            account = self.default_account_id
            if balance >= 0.0:
                debit = 0.0
                credit = balance
            else:
                debit = -balance
                credit = 0.0

            if not account:
                raise ValidationError(_(
                    'Esta intentando crear un asiento automático desbalanceado'
                    '. Es posible que haya un error en el informe o '
                    'esté faltando configurar la cuenta de contrapartida en el'
                    'diario.'))
            lines_vals.append({
                'partner_id': self.settlement_partner_id.id,
                'name': self.name,
                'debit': debit,
                'credit': credit,
                'account_id': account.id,
            })

        # convertimos los vals a formato para crear en o2m
        line_ids = []
        for vals in lines_vals:
            line_ids.append((0, False, vals))

        move_vals = {
            'ref': self._context.get('entry_ref'),
            'date': self._context.get('entry_date', fields.Date.today()),
            'journal_id': self.id,
            'company_id': self.company_id.id,
            'line_ids': line_ids,
        }
        return move_vals

####################################
# Métodos de liquidación por reporte
####################################


#################################
# Métodos de liquidación por tags
#################################

    def _get_tax_settlement_move_lines_by_tags(self):
        """
        Funcion que devuelve apuntes a liquidar por este diario
        """
        self.ensure_one()
        return self.env['account.move.line'].search(
            self._get_tax_settlement_lines_domain_by_tags() + [
                ('tax_state', '=', 'to_settle')])

    def _get_tax_settlement_lines_domain_by_tags(self):
        """
        Funcion que devuelve apuntes contables que se liquidan con este diario
        (liquidados o no)
        """
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('tax_repartition_line_id.tag_ids', 'in', self.settlement_account_tag_ids.ids),
        ]

        from_date = self._context.get('from_date')
        if from_date:
            domain.append(('date', '>=', from_date))

        to_date = self._context.get('to_date')
        if to_date:
            domain.append(('date', '<=', to_date))

        return domain

    def _get_tax_settlement_lines_domain_by_tags_accounts(self):
        """
        Funcion que devuelve apuntes contables de cuentas contables de
        impuestos que usen los tags.
        necesitamos esta busqueda así ya que actualmente estamos buscando por
        tags en impuestos y, para calcular saldo de las cuentas, necesitamos
        buscar por cuenta ya que las liquidaciones no tienen nada seteado en
        tax_line_id / tax_repartition_line_id
        """
        self.ensure_one()
        rep_lines = self.env['account.tax.repartition.line'].search([
            ('company_id', '=', self.company_id.id),
            ('tag_ids', 'in', self.settlement_account_tag_ids.ids),
        ])
        domain = [
            ('company_id', '=', self.company_id.id),
            ('account_id', 'in', rep_lines.mapped('account_id').ids),
        ]

        from_date = self._context.get('from_date')
        if from_date:
            domain.append(('date', '>=', from_date))

        to_date = self._context.get('to_date')
        if to_date:
            domain.append(('date', '<=', to_date))

        return domain

###################################
# Métodos de generación de archivos
###################################

    def get_tax_settlement_files_values(self, move_lines):
        """
        Funciónque de devuelve lista de diccionarios con "nombre de archivo"
        y "contenido de archivo" para todos los apuntes seleccionados
        Ej:
        [{'txt_filename': 'Nombre', 'txt_content': 'Contenido'}
        """
        self.ensure_one()
        draft_lines = move_lines.filtered(lambda x: x.move_id.state == 'draft')
        if draft_lines:
            raise ValidationError(_(
                'A seleccionado apuntes contables de asientos en borrador. '
                'Solo puede generar el txt de apuntes de asientos publicados. Apuntes: %s') % draft_lines.ids)
        _logger.info(
            "Getting tax settlement tax values for '%s'" % (self.name))
        if self.settlement_tax and hasattr(
                self, '%s_files_values' % self.settlement_tax):
            return getattr(
                self, '%s_files_values' % self.settlement_tax)(move_lines)
        return []

    # viejo código cuandolo haciamos con qweb
    # report = self.settlement_file_template
    # if not report:
    #     raise ValidationError(_(
    #         'No settlement file template found for journal "%s"') % (
    #         self.name))

    # lang = self.env['res.lang'].search(
    #     [('code', '=', self.env.user.lang)], limit=1)
    # date_format = lang.date_format or DEFAULT_SERVER_DATE_FORMAT

    # def formatLangDate(date):
    #     date_dt = datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT)
    #     return date_dt.strftime(
    #         date_format.encode('utf-8')).decode('utf-8')

    # def get_line_tax_base(move_line):
    #     return sum(move_line.move_id.line_ids.filtered(
    #         lambda x: move_line.tax_line_id in x.tax_ids).mapped(
    #         'balance'))

    # # mas simple podriamos usar "'%016.2f'" como en sicore para los otros
    # # pero tener en cuenta que habria que hacer replace si se requiere ","
    # # como separador decimal
    # def format_amount(amount, padding=15, decimals=2, sep=""):
    #     if amount < 0:
    #         template = "-{:0>%dd}" % (padding - 1 - len(sep))
    #     else:
    #         template = "{:0>%dd}" % (padding - len(sep))
    #     res = template.format(
    #         int(round(abs(amount) * 10**decimals, decimals)))
    #     if sep:
    #         res = "{0}{1}{2}".format(res[:-decimals], sep, res[-decimals:])
    #     return res

    # values = {
    #     'get_line_tax_base': get_line_tax_base,
    #     'formatLangDate': formatLangDate,
    #     'format_amount': format_amount,
    #     # 'formatLang': formatLang,
    #     'journal': self,
    #     'move_lines': move_lines,
    #     'company': self.company_id,
    #     're': re,
    # }
    # txt_content = self.env['report'].render(report.id, values)
    # # TODO mejorar, por ahora, de manera horrible, borramos todas las
    # # lineas vacias
    # txt_content = txt_content.replace('\n\n', '\n')
    # return {
    #     'txt_filename': self.name,
    #     'txt_content': txt_content,
    # }
