from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression
from datetime import datetime


class L10nArCaea(models.Model):

    _name = 'l10n.ar.caea'
    _description = 'CAEA (Anticipated Electronic Authorization Code)'
    _order = "date_from desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _sql_constraints = [
        ('unique_caea_name', 'unique (company_id,name)', 'CAEA already exists!'),
    ]

    name = fields.Char(copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    informed = fields.Boolean(compute="_compute_informed", store=True, readonly=False, string="Reported to AFIP")

    process_deadline = fields.Date("Fecha Vencimiento", readonly=True)        # FchTopeInf
    process_datetime = fields.Datetime("Fecha de Solicitud", readonly=True)    # FchProceso

    move_ids = fields.One2many('account.move', 'l10n_ar_caea_id')
    moves_to_inform_ids = fields.One2many('account.move', compute='_compute_moves_to_inform_ids')
    moves_count = fields.Integer("Moves", compute='compute_moves_count')

    def name_get(self):
        res = []
        for record in self:
            if record.date_from:
                res.append((record.id, '%s (%s)' % (record.date_from.strftime('%B %Y'), record.name)))
            else:
                res.append((record.id, '/'))
        return res

    # TODO not sure why but this is not working :(. not priority
    # @api.model
    # def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
    #     args = args or []
    #     if operator == 'ilike' and not(name or '').strip():
    #         domain = []
    #     else:
    #         domain = ['|', ('name', operator, name), ('date_from', operator, name)]
    #     return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    # Compute Methods

    def compute_moves_count(self):
        """ Calcula el total de las facturas asociadas al CAEA actual """
        # retrieve all children partners and prefetch 'parent_id' on them
        for rec in self:
            rec.moves_count = len(rec.move_ids)

    @api.depends('move_ids', 'move_ids.l10n_ar_afip_result')
    def _compute_informed(self):
        """ Si tienes account.move vinculados y todos estan informados (cae result esta aprobado o observado).
        NOTA: Si no tiene movimientos, mediante cron lo ponemos True luego de informarlo """
        pending_to_inform = self.filtered(lambda x: x.move_ids.filtered(
            lambda y: y.state == 'posted' and y.l10n_ar_afip_result not in ['A', 'O']))
        pending_to_inform.informed = False
        (self - pending_to_inform).informed = True

    def _compute_moves_to_inform_ids(self):
        for rec in self:
            rec.moves_to_inform_ids = rec.move_ids.filtered(lambda x: x.state == 'posted' and x.l10n_ar_afip_result not in ['A', 'O'])

    # Onchange Methods

    @api.onchange('date_to', 'date_from')
    def _onchange_dates(self):
        """ Fix the date to and end to dates given by the user """

        if self.date_from:
            init_of_month = fields.Date.start_of(self.date_from, "month")
            end_of_month = fields.Date.end_of(self.date_from, "month")
            fornight = fields.Date.add(self.date_from, day=15)
            if self.date_from.day <= 15:
                self.date_from = init_of_month
                self.date_to = fornight
            else:
                self.date_from = fields.Date.add(fornight, days=1)
                self.date_to = end_of_month

    # Action / Button Methods

    def action_view_moves(self):
        """This function returns an action that displays the moves related to this CAEA"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('l10n_ar_caea_id', '=', self.name)],
        }

    def action_request_caea_from_afip(self):
        """ Get CAEA number from AFIP """
        self.ensure_one()

        afip_ws = self.get_afip_ws()
        client, auth = self.company_id._l10n_ar_get_connection(afip_ws)._get_client()

        period = self.date_from.strftime('%Y%m')
        order = '1' if self.date_to.day < 16 else '2'

        # 1 Consultar si ya existe, traernos el dato de AFIP al Odoo
        response = client.service.FECAEAConsultar(auth, Periodo=period, Orden=order)
        if response.Errors:
            if response.Errors.Err[0].Code == 602:
                # No existe el CAEA asi que intentaremos generarlo
                pass
            else:
                raise UserError('No se consiguió un CAEA %s' % str(response.Errors))

        # 2 Si no existe CAEA entonces pedir a AFIP para crearlo
        if not response.ResultGet.CAEA:
            response = client.service.FECAEASolicitar(auth, Periodo=period, Orden=order)

            # Si ya existe no genero sino que consulto el CAE
            if response.Errors:
                if response.Errors.Err[0].Code == 15006:
                    raise UserError(_('No se pudo generar el CAEA en AFIP. %s') % response.Errors.Err[0].Msg)

                raise UserError(_('No se pudo crear el CAEA %s') % str(response.Errors))

        result = response.ResultGet
        self.name = result.CAEA

        self.process_deadline = datetime.strptime(result.FchTopeInf, "%Y%m%d").date()
        self.process_datetime = datetime.strptime(result.FchProceso, "%Y%m%d%H%M%S")

        if result.Observaciones:
            return_info = ''.join(['\n* Code %s: %s' % (ob.Code, ob.Msg) for ob in result.Observaciones.Obs])
            self.message_post(
                body='<p><b>' + _('AFIP Observations') + '</b></p><p><i>%s</i></p>' % (return_info))

        # Improve process Errors and Events
        # result.Errors       Err (Code, Msg)
        # result.Events       Evt (Code, Msg)

    def action_report_to_afip(self):
        self.ensure_one()
        today = fields.Date.context_today(self)

        if self.moves_to_inform_ids:
            res = []
            try:
                res = self.action_send_invoices()
                if res:
                    raise UserError(_('There was a problem with one of the invoices you want to report, please fix it and then try to inform again'))
            finally:
                self.message_post(body='<p><b>' + _('AFIP Messages V2') +
                                  '</b></p><p><ul><li>%s</li></ul></p>' % ('</li><li>'.join(res)))
        else:
            # Si se vencio el periodo y no tengo facturas, reportar asi sin facturas
            if self.date_to < today and not self.move_ids:
                return self.action_report_no_invoices()
            else:
                raise UserError(_('There is not invoices to report. if you like to inform without invoices you will need to way until Date to'))

    # CRON Methods

    def cron_request_caea(self):
        """ Create CAEA in Odoo extracting infro from AFIP:
        * If current fortnight is not created then create the CAE for today
        * If can create the CAEA for next fortnight then we also create ir (5 days previous to the fortnight) """
        # TODO need to re test this method, change logic?
        today = fields.Date.context_today(self)

        company_ids = self.env['res.company'].search([('l10n_ar_use_caea', '=', True)])
        caes = self

        for company_id in company_ids:

            # Encontrar si ya existe el CAEA para la fecha actual
            caea = self.search([('date_from', '>=', today), ('date_to', '<', today)])

            if caea:    # Si es asi no creamos nada
                continue

            request_date = today
            period = request_date.strftime('%Y%m')
            order = '1' if request_date.day < 16 else '2'

            end_of_month = fields.Date.end_of(request_date, "month")
            if order == '1':
                date_from = fields.Date.start_of(request_date, "month")
                date_to = fields.Date.add(request_date, day=15)
            else:
                date_from = fields.Date.add(request_date, day=16)
                date_to = end_of_month

            # Creamos el CAE para la fecha de hoy
            caes += self.create({'name': period, 'date_from': date_from, 'date_to': date_to, 'company_id': company_id.id})

            # Crear CAEA proxima quincena:
            # Podrá ser solicitado dentro de cada quincena y hasta 5 (cinco) días corridos anteriores al
            # comienzo de cada quincena.
            middle_of_month = fields.Date.add(today, day=15)
            if (middle_of_month - today).days <= 5:     # Calculo proxima quincena en el mismo mes
                caes += self.create({'name': period, 'date_from': fields.Date.add(request_date, day=16), 'date_to': end_of_month, 'company_id': company_id.id})
            elif (end_of_month - today).days <= 5:    # Calculo proxima quicena en el mes siguiente
                nextmonth = fields.Date.add(end_of_month, day=1)
                period = nextmonth.strftime('%Y%m')
                caes += self.create({'name': period, 'date_from': nextmonth, 'date_to': fields.Date.add(nextmonth, day=15), 'company_id': company_id.id})

        for caea in caes:
            caea.action_request_caea_from_afip()

    def cron_send_caea_invoices(self):
        """ send CAEA invoices to AFIP each day"""
        today = fields.Date.context_today(self)
        caea_ids = self.search([
            ('date_from', '<=', fields.Date.add(today, days=1)),
            ('date_to', '>=', fields.Date.add(today, days=1)),
        ])
        for caea in caea_ids:
            caea.action_send_invoices()

    def cron_inform_expired_caea(self):
        inform_expired = self.search([
            ('date_to', '<', fields.Date.context_today(self)),
            ('move_ids', '=', False)])
        for rec in inform_expired.filtered(lambda x: not x.informed):
            rec.action_report_no_invoices()

    # Helper Methods

    def get_afip_ws(self):
        """ por los momentos siempre va a ser este tipo, mas adelante si se implementan otros como el de detalle producto
        debemos extender este metodo """
        return 'wsfe'

    def action_send_invoices(self):
        # A futuro, tener en cuenta si estamos en modo contingencia debemos de salir de alli parapoder repotar.
        afip_ws = self.get_afip_ws()
        return_info_all = []
        for inv in self.moves_to_inform_ids.sorted(key=lambda r: r.invoice_date and r.l10n_latam_document_number):
            client, auth, transport = inv.company_id._l10n_ar_get_connection(afip_ws)._get_client(return_transport=True)
            return_info = inv._l10n_ar_do_afip_ws_request_caea(client, auth, transport)
            if return_info:
                return_info_all.append("<strong>%s</strong> %s" % (inv.name, return_info))
        if return_info_all:
            self.message_post(body='<p><b>' + _('AFIP Messages') +
                              '</b></p><p><ul><li>%s</li></ul></p>' % ('</li><li>'.join(return_info_all)))

        return return_info_all

    def get_caea_pos(self):
        """ Se conecta a AFIP para obtener cuales son los diarios CAEA que debemos informar """
        self.ensure_one()
        afip_ws = self.get_afip_ws()
        connection = self.company_id._l10n_ar_get_connection(afip_ws)
        client, auth = connection._get_client()
        journals = self.env['account.journal']
        if afip_ws == 'wsfe':
            response = client.service.FEParamGetPtosVenta(auth)
            if response.ResultGet:
                pos_numbers = []
                for pdv in response.ResultGet.PtoVenta:
                    if pdv.EmisionTipo.startswith('CAEA') and pdv.Bloqueado == 'N':
                        pos_numbers.append(int(pdv['Nro']))
                journals |= self.env['account.journal'].search([('l10n_ar_afip_pos_number', 'in', pos_numbers)])
        else:
            raise UserError(
                _('"Check Available AFIP PoS CAEA" is not implemented for webservice %s', self.l10n_ar_afip_ws))

        return journals

    def action_report_no_invoices(self):
        """ Este método se conecta a AFIP y reporta este CAEA como listo ya que vencío y no tiene movimientos """
        self.ensure_one()
        afip_ws = self.get_afip_ws()

        client, auth = self.company_id._l10n_ar_get_connection(afip_ws)._get_client()
        if afip_ws == 'wsfe':
            # Update actives Journals
            caea_journals = self.get_caea_pos()

            journal_w_moves = self.env['account.move'].search([
                ('journal_id', 'in', caea_journals.ids),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
            ]).mapped('journal_id')

            no_invoices_journal_ids = caea_journals - journal_w_moves
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
                    return_info += "<p><strong>* POS %s</strong> %s</p>" % (
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

            self.message_post(body=_('Este CAEA esta vencido y no tiene comprobantes asociados'))
            self.message_post(
                body='<p><b>' + _('AFIP Messages') + '</b></p><p><i>%s</i></p>' % (return_info))
            self.informed = True

        else:
            raise UserError(
                _('"Report CAEA with not invoices is not implemented" for webservice %s', self.l10n_ar_afip_ws))
