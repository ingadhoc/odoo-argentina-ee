from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime


class L10nArCaea(models.Model):

    _name = 'l10n.ar.caea'
    _description = 'CAEA (Anticipated Electronic Authorization Code)'
    _order = "date_from desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _sql_constraints = [
        ('unique_caea_name', 'unique (company_id,name)', 'CAEA already exists!'),
        ('unique_caea_periods', 'unique (company_id,period,order)', 'CAEA request already exists!')
    ]

    name = fields.Char(copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string='from')
    date_to = fields.Date(string='to')
    informed = fields.Boolean(compute="compute_informed", store=True, readonly=False)

    process_deadline = fields.Date()        # FchTopeInf    Fecha de tope para informar los comprobantes vinculados al CAEA
    process_datetime = fields.Datetime()    # FchProceso    Fecha de proceso, formato yyyymmddhhmiss

    order = fields.Selection([('1', 'first Fortnight'), ('2', 'second Fortnight')], string='Fortnight', default='')
    period = fields.Char(size=6)

    # NTH? revisar si lo queremos realmente
    year = fields.Integer()
    month = fields.Selection(
        [('01', 'January'),
         ('02', 'February'),
         ('03', 'March'),
         ('04', 'April'),
         ('05', 'May'),
         ('06', 'June'),
         ('07', 'July'),
         ('08', 'August'),
         ('09', 'September'),
         ('10', 'October'),
         ('11', 'November'),
         ('12', 'December')],
        string='Month',
    )

    move_ids = fields.One2many('account.move', 'l10n_ar_caea_id')
    moves_count = fields.Integer("Moves", compute='compute_moves_count')
    journal_ids = fields.Many2many('account.journal', string='Autorized CAEA journals')

    # Compute Methods

    def compute_moves_count(self):
        """ Calcula el total de las facturas asociadas al CAEA actual """
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

    # Onchange Methods

    @api.onchange('month', 'year')
    def _onchange_month_year(self):
        if self.year and self.month:
            self.period = str(self.year) + self.month

    # Action / Button Methods

    def action_view_moves(self):
        """This function returns an action that displays the moves related to this CAEA"""
        action = self.env['ir.actions.act_window']._for_xml_id('l10n_ar_edi_caea.l10n_ar_caea_action')
        action['domain'] = [('l10n_ar_caea', '=', self.name)]
        return action

    # CRON Methods

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
                caea.action_request_caea_from_afip()

    # Helper Methods

    def get_afip_ws(self):
        """ por los momentos siempre va a ser este tipo, mas adelante si se implementan otros como el de detalle producto
        debemos extender este metodo """
        return 'wsfe'

    def action_get_caea_pos(self):
        """ Se conecta a AFIP ara obtener cuales son los diarios CAEA que debemos informar """
        # TODO test it
        self.ensure_one()
        afip_ws = self.get_afip_ws()
        connection = self.company_id._l10n_ar_get_connection(afip_ws)
        client, auth = connection._get_client()
        if afip_ws == 'wsfe':
            response = client.service.FEParamGetPtosVenta(auth)
            if response.ResultGet:
                journal_ids = False
                for pdv in response.ResultGet.PtoVenta:
                    pos_numbers = []
                    if pdv.EmisionTipo.startswith('CAEA') and pdv.Bloqueado == 'N':
                        pos_numbers.append(int(pdv['Nro']))
                    journal_ids = self.env['account.journal'].search(
                        [('l10n_ar_afip_pos_number', 'in', pos_numbers)])
                    # TODO KZ agregar aca que esten configurados como de tipo CAEA?

                if journal_ids:
                    self.journal_ids = [(6, 0, journal_ids.ids)]
        else:
            raise UserError(
                _('"Check Available AFIP PoS" is not implemented for webservice %s', self.l10n_ar_afip_ws))

    def action_request_caea_from_afip(self):
        """ Get CAEA from AFIP """
        self.ensure_one()
        afip_ws = self.get_afip_ws()
        client, auth, _transport = self.company_id._l10n_ar_get_connection(afip_ws)._get_client(return_transport=True)

        period = self.date_from.strftime('%Y%m')
        order = '1' if self.date_to.day < 16 else '2'

        # 1 Consultar si ya existe, traernos el dato al Odoo
        result = client.service.FECAEAConsultar(auth, Periodo=period, Orden=order)
        if result.Errors:
            if result.Errors.Err[0].Code == 602:
                # No existe el CAEA asi que intentaremos generarlo
                pass
            else:
                raise UserError('No se consiguió un CAEA %s' % str(result.Errors))

        # 2 Si no existe CAEA entonces pedir a AFIP para crearlo
        if not result.ResultGet.CAEA:
            result = client.service.FECAEASolicitar(auth, Periodo=period, Orden=order)

            # Si ya existe no genero sino que consulto el CAE
            if result.Errors:
                if result.Errors.Err[0].Code == 15006:
                    raise UserError(_('No se pudo generar el CAEA en AFIP. %s') % result.Errors.Err[0].Msg)

                raise UserError(_('No se pudo crear el CAEA %s') % str(result.Errors))

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
        inform_expired = self.search(
            [('informed', '!=', True),
             ('date_to', '<', fields.Date.context_today(self)),
             ('move_ids', '=', False)])
        for rec in inform_expired:
            rec.message_post(body=_('Este CAEA esta vencido y no tiene comprobantes asociados, se procede a reportar a AFIP'))
            rec.action_report_no_invoices()
            rec.informed = True

    def action_report_no_invoices(self):
        """ Este método se conecta a AFIP y reporta este CAEA como listo ya que vencío y no tiene movimientos """
        # TODO KZ need to test it
        self.ensure_one()
        afip_ws = self.get_afip_ws()

        client, auth, _transport = self.company_id._l10n_ar_get_connection(afip_ws)._get_client(return_transport=True)
        if afip_ws == 'wsfe':
            # Update actives Journals
            self.action_get_caea_pos()
            journal_ids = self.env['account.move'].search([
                ('journal_id', 'in', self.journal_ids.ids),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
            ]).mapped('journal_id')

            no_invoices_journal_ids = self.journal_ids - journal_ids
            ws_method = 'FECAEASinMovimientoInformar'

            return_info = ''
            for report_journal in no_invoices_journal_ids:
                request_data = {
                    'PtoVta': report_journal.l10n_ar_afip_pos_number, 'CAEA': self.name}
                try:
                    client.create_message(client.service, ws_method,
                                          auth, request_data
                                          )
                except Exception as error:
                    raise UserError(repr(error))

                response = client.service[ws_method](
                    auth, PtoVta=report_journal.l10n_ar_afip_pos_number, CAEA=self.name
                )
                if response.Resultado == 'A':
                    return_info += "<p><strong>POS %s</strong> %s</p>" % (
                        report_journal.l10n_ar_afip_pos_number,
                        _('Reported with no invoices successful')
                    )
                else:
                    return_info += "<p><strong>POS %s</strong> %s</p>" % (
                        report_journal.l10n_ar_afip_pos_number,
                        _('Error cant reported with no invoices')
                    )
                if response.Errors:
                    return_info += ''.join(
                        ['\n* Code %s: %s' % (err.Code, err.Msg) for err in response.Errors.Err])

                if response.Events:
                    return_info += ''.join(
                        ['\n* Code %s: %s' % (evt.Code, evt.Msg) for evt in response.Events.Evt])

            self.message_post(
                body='<p><b>' + _('AFIP Messages') + '</b></p><p><i>%s</i></p>' % (return_info))
            self.state = 'reported'

        else:
            raise UserError(
                _('"Check Available AFIP PoS" is not implemented for webservice %s', self.l10n_ar_afip_ws))
