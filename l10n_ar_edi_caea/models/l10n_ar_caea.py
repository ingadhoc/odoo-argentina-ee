from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime


class L10nArCaea(models.Model):

    _name = 'l10n.ar.caea'
    _description = 'CAEA (Anticipated Electronic Authorization Code)'
    _order = "date_from desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _sql_constraints = [
        ('unique_caea', 'unique (company_id,name)', 'CAEA already exists!'),
    ]
    name = fields.Char(copy=False)

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string='from')
    date_to = fields.Date(string='to')
    informed = fields.Boolean(compute="compute_informed", store=True, readonly=False)

    order = fields.Selection([('1', 'first Fortnight'), ('2', 'second Fortnight')], string='Fortnight')

    period = fields.Char(size=6)
    process_deadline = fields.Date()        # FchTopeInf    Fecha de tope para informar los comprobantes vinculados al CAEA
    process_datetime = fields.Datetime()    # FchProceso    Fecha de proceso, formato yyyymmddhhmiss

    # NTH? revisar si lo queremos realmente
    # year = fields.Integer()
    # month = fields.Selection(
    #     [('01', 'January'),
    #      ('02', 'February'),
    #      ('03', 'March'),
    #      ('04', 'April'),
    #      ('05', 'May'),
    #      ('06', 'June'),
    #      ('07', 'July'),
    #      ('08', 'August'),
    #      ('09', 'September'),
    #      ('10', 'October'),
    #      ('11', 'November'),
    #      ('12', 'December')],
    #     string='Month',
    # )

    move_ids = fields.One2many('account.move', 'l10n_ar_caea_id')
    moves_count = fields.Integer("Moves", compute='compute_moves_count')

    def compute_moves_count(self):
        # retrieve all children partners and prefetch 'parent_id' on them
        for rec in self:
            rec.moves_count = len(rec.move_ids)

    def compute_informed(self):
        """si tiene account.move vinculados y todos estan informados (cae result != False)
        si no tiene movimientos, mediante cron lo ponemos True luego de informarlo
        """
        all_move_informed = self.filtered(lambda x: x.move_ids and not x.move_ids.filtered(lambda x: not x.l10n_ar_afip_result))
        all_move_informed.informed = True
        (self - all_move_informed).informed = False

    def action_view_moves(self):
        """This function returns an action that displays the moves related to this CAEA"""
        action = self.env['ir.actions.act_window']._for_xml_id('l10n_ar_edi_caea.l10n_ar_caea_action')
        action['domain'] = [('l10n_ar_caea', '=', self.name)]
        return action

    def cron_request_caea(self):
        """ Create CAEA in Odoo extracting infro from AFIP:
        * If current fortnight is not created then create the CAE for today
        * If can create the CAEA for next fortnight then we also create ir (5 days previous to the fortnight) """
        today = fields.Date.context_today(self)

        company_ids = self.env['res.company'].search([('l10n_ar_use_caea', '=', True)])
        caes = self

        for company_id in company_ids:

            # Encontrar si ya existe el CAEA para la fecha actual
            caea = self.search([('date_from', '>=', today), ('date_to', '<', today)])
            # caea = self.search([('name', '=', period), ('order', '=', order), ('company_id', '=', company_id.id)])

            if caea:    # Si es asi no creo nada
                continue

            request_date = today
            # request_date = today + fields.Date.add(days=7) TODO review why 7 dias?
            period = request_date.strftime('%Y%m')
            order = '1' if request_date.day < 16 else '2'

            # Creo el CAE para la fecha de hoy
            caes += self.create({'name': period, 'order': order, 'company_id': company_id.id})

            # Crear caea proxima quincena?
            # Podrá ser solicitado dentro de cada quincena y hasta 5 (cinco) días corridos anteriores al comienzo
            # de cada quincena.
            end_of_month = fields.Date.end_of(today, "month")
            middle_of_month = fields.Date.add(today, day=15)
            import pdb
            pdb.set_trace()
            if (end_of_month - today).days <= 5 or (middle_of_month - today).days <= 5:
                caes += self.create({'name': period, 'order': order, 'company_id': company_id.id})

        if caes:
            for caea in caes:
                caea.request_caea_from_afip()

    def request_caea_from_afip(self):
        """ Get CAEA from AFIP """
        self.ensure_one()
        afip_ws = 'wsfe'
        client, auth, _transport = self.company_id._l10n_ar_get_connection(afip_ws)._get_client(return_transport=True)

        period = self.date_from.strftime('%Y%m')
        order = '1' if self.date_to.day < 16 else '2'

        # 1 Consultar si ya existe, traernos el dato al Odoo
        result = client.service.FECAEAConsultar(auth, Periodo=period, Orden=order)
        import pdb
        pdb.set_trace()
        if result.Errors:
            if result.Errors.Err[0].Code == 602:
                # No existe el CAEA pero intentamos generarlo
                pass
            else:
                raise UserError('No se consiguio un CAEA %s' % str(result.Errors))

        # 2 Si no existe CAEA entonces pedir a AFIP para crearlo
        if not result.ResultGet.CAEA:
            result = client.service.FECAEASolicitar(auth, Periodo=period, Orden=order)

            # Si ya existe no genero sino que consulto el CAE
            if result.Errors:
                raise UserError('No se pudo crear el CAEA %s' % str(result.Errors))

        result = result.ResultGet
        self.name = result.CAEA
        # self.date_from = result.FchVigDesde       20220501 datetime.strptime(result.FchVigDesde, "%Y%m%d").date()
        # self.date_to = result.FchVigHasta
        self.period = result.Periodo
        self.order = str(result.Orden)

        # TODO tomar en cuenta que debemos hacer el cambio a TZ AR
        self.process_deadline = datetime.strptime(result.FchTopeInf, "%Y%m%d").date()
        self.process_datetime = datetime.strptime(result.FchProceso, "%Y%m%d%H%M%S")

        if result.Observaciones:
            return_info = ''.join(['\n* Code %s: %s' % (ob.Code, ob.Msg) for ob in result.Observaciones.Obs])
            self.message_post(
                body='<p><b>' + _('AFIP Observations') + '</b></p><p><i>%s</i></p>' % (return_info))

        # TODO Improve process this
        # result.Errors       Err (Code, Msg)
        # result.Events       Evt (Code, Msg)

    def _l10n_ar_do_afip_ws_request_caea(self, client, auth, transport, ws_method='FECAEASolicitar'):
        self.ensure_one()
        try:
            client.create_message(client.service, ws_method,
                                  auth, Orden=self.order, Periodo=self.period)
        except Exception as error:
            raise UserError(repr(error))
        response = client.service[ws_method](
            auth, Orden=self.order, Periodo=self.period)
        if response['Errors']:
            if response['Errors']['Err'][0]['Code'] == 15008:
                response = self._l10n_ar_do_afip_ws_request_caea(
                    client, auth, transport, 'FECAEAConsultar')
                return response
            else:
                raise UserError(repr(response['Errors']))
        if response['Events']:
            raise UserError(repr(response['Events']))

        return response['ResultGet']

    def cron_send_caea_invoices(self):
        """ send CAEA invoices to AFIP each day"""
        today = fields.Date.context_today(self)
        caea_ids = self.search([
            ('date_from', '<=', today + fields.Date.add(days=1)),
            ('date_to', '>=', today + fields.Date.add(days=1)),
            ('state', '=', 'active')
        ])
        for caea_id in caea_ids:
            caea_id.action_send_invoices()

    def cron_inform_expired_caea(self):
        res = self.search[('informed', '!=', True), ('date_to', '<', fields.Date.context_today(self))]
        print("vencidos sin informar %s" % res)
        # Todo informar CAEA que esta venido intentar reportarlo y luego marca informado = True
