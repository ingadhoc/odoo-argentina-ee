from odoo import _, api, models, fields
from odoo.exceptions import UserError
from odoo.tools import plaintext2html
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):

    _inherit = 'account.move'

    l10n_ar_caea_id = fields.Many2one('l10n.ar.caea', copy=False)
    is_caea = fields.Boolean(compute="compute_is_caea")
    l10n_ar_afip_pos_system = fields.Selection(related="journal_id.l10n_ar_afip_pos_system")
    l10n_ar_afip_result = fields.Selection(selection_add=[('R', 'Rejected in AFIP')], string="AFIP Result")
    l10n_caea_info = fields.Char(compute="compute_is_caea")

    @api.depends("journal_id")
    def compute_is_caea(self):
        """ Soy CAEA si:
        1. Soy una factura dentro de diario CAEA
        2. Soy una factura electronica pero estoy en un diario no CAEA y estoy en modo contingencia  """
        caea_invoices = self.filtered(
            lambda x: x.journal_id.l10n_ar_afip_pos_system and 'CAEA' in x.journal_id.l10n_ar_afip_pos_system)
        contg_invoices = self.filtered(
            lambda x: x.journal_id.l10n_ar_afip_ws == 'wsfe' and 'CAEA' not in x.journal_id.l10n_ar_afip_pos_system
            and x.journal_id.company_id.l10n_ar_contingency_mode)

        missing_config = contg_invoices.filtered(lambda x: not x.journal_id.l10n_ar_contingency_journal_id)
        if missing_config:
            missing_config.l10n_caea_info = _("IMPORTANTE: Estas en modo contigencia pero no estan configurandos los darios de contingencia del diario seleccionado")
            contg_invoices -= missing_config

        cae_invoices = caea_invoices + contg_invoices
        cae_invoices.is_caea = True
        (self - cae_invoices).is_caea = False
        (self - missing_config).l10n_caea_info = False

    def _l10n_ar_do_afip_ws_request_cae(self, client, auth, transport):
        """ Extendemos el metodo original que termina haciendo lo de factura electrónica para integrar
        lo de CAEA, dicho caso no reportamos a AFIP de manera inmediata """
        # TODO KZ hacer cuando implementemos contingencia or .journal_id.caea_journal_id
        cae_invoices = self.filtered(lambda x: x.is_caea)
        cae_invoices._l10n_ar_caea_validate_local()

        return super(AccountMove, self - cae_invoices)._l10n_ar_do_afip_ws_request_cae(client=client, auth=auth, transport=transport)

    def _l10n_ar_do_afip_ws_request_caea(self, client, auth, transport):
        """ Submits the invoice information to AFIP and gets a response of AFIP in return on CAEA Moneda

        Similar to what we have in _l10n_ar_do_afip_ws_request_cae method"""

        for inv in self.filtered(lambda x: x.journal_id.l10n_ar_afip_ws and (x.is_caea and x.l10n_ar_afip_result not in ['A', 'O'])):
            _logger.info("Reporting CAEA Invoice to AFIP %s", inv.display_name)
            afip_ws = inv.journal_id.l10n_ar_afip_ws
            errors = obs = events = ''
            request_data = False
            return_codes = []
            values = {}

            # We need to call a different method for every webservice type and assemble the returned errors if they exist
            if afip_ws == 'wsfe':
                ws_method = 'FECAEARegInformativo'
                request_data = inv.wsfe_get_cae_request(client)
                self._ws_verify_request_data(client, auth, ws_method, request_data)
                response = client.service[ws_method](auth, request_data)
                if response.FeDetResp:
                    result = response.FeDetResp.FECAEADetResponse[0]
                    if result.Observaciones:
                        obs = ''.join(['\n* Code %s: %s' % (ob.Code, ob.Msg) for ob in result.Observaciones.Obs])
                        return_codes += [str(ob.Code) for ob in result.Observaciones.Obs]
                    values = {'l10n_ar_afip_result': result.Resultado}
                    if result.Resultado == 'A':
                        values.update({'l10n_ar_afip_auth_mode': 'CAEA',
                                       'l10n_ar_afip_auth_code': result.CAEA and str(result.CAEA) or ""})

                if response.Errors:
                    errors = ''.join(['\n* Code %s: %s' % (err.Code, err.Msg) for err in response.Errors.Err])
                    return_codes += [str(err.Code) for err in response.Errors.Err]
                if response.Events:
                    events = ''.join(['\n* Code %s: %s' % (evt.Code, evt.Msg) for evt in response.Events.Evt])
                    return_codes += [str(evt.Code) for evt in response.Events.Evt]
            else:
                raise UserError(_('Reporting invoices in CAE in %s is not implemented') % afip_ws)

            return_info = inv._prepare_return_msg(afip_ws, errors, obs, events, return_codes)
            afip_result = values.get('l10n_ar_afip_result')
            xml_response, xml_request = transport.xml_response, transport.xml_request
            if afip_result not in ['A', 'O']:
                if not self.env.context.get('l10n_ar_invoice_skip_commit'):
                    self.env.cr.rollback()
                if inv.exists():
                    # Only save the xml_request/xml_response fields if the invoice exists.
                    # It is possible that the invoice will rollback as well e.g. when it is automatically created:
                    #   * creating credit note with full reconcile option
                    #   * creating/validating an invoice from subscription/sales
                    inv.sudo().write({
                        'l10n_ar_afip_xml_request': xml_request, 'l10n_ar_afip_xml_response': xml_response,
                        'l10n_ar_afip_result': afip_result})
                if not self.env.context.get('l10n_ar_invoice_skip_commit'):
                    self.env.cr.commit()
                return return_info
            values.update(l10n_ar_afip_xml_request=xml_request, l10n_ar_afip_xml_response=xml_response)
            inv.sudo().write(values)
            if return_info:
                inv.message_post(body='<p><b>' + _('AFIP Messages') + '</b></p>' + (plaintext2html(return_info, 'em')))

    def _l10n_ar_caea_validate_local(self):
        """ Add CAEA number to the invoices that we need to validate and that will be inform later with CAEA """
        for inv in self:
            _logger.info("Validando Factura CAEA solo en local %s", inv.display_name)
            # TODO KZ oportunidad de mejora. mover el calculo del afip_caea previo al loop. desde alli ver los caea d
            # todas las compa;ias y hacer early return si no existe.
            afip_caea = self.ensure_caea()
            values = {
                'l10n_ar_afip_auth_mode': 'CAEA',
                'l10n_ar_caea_id': afip_caea.id,
                'l10n_ar_afip_auth_code': afip_caea.name,
                'l10n_ar_afip_auth_code_due': self.invoice_date,
                'l10n_ar_afip_result': '',
            }
            inv.sudo().write(values)

    def get_active_caea(self):
        """Obtiene el CAEA actual que se puede usar para dicha factura """
        self.ensure_one()
        return self.env['l10n.ar.caea'].search([
            ('company_id', '=', self.company_id.id),
            ('date_from', '<=', self.date), ('date_to', '>=', self.date),
            ('name', '!=', False)])

    def ensure_caea(self):
        """Obtiene el CAEA actual que se puede usar para dicha factura """
        afip_caea = self.get_active_caea()
        if not afip_caea:
            raise UserError(_('Dont have an active or valid CAEA'))
        return afip_caea

    def wsfe_get_cae_request(self, client=None):
        """ Add more info needed for report to webserive with CAEA"""
        self.ensure_one()
        res = super().wsfe_get_cae_request(client=client)
        if self.l10n_ar_afip_ws == 'wsfe' and self.is_caea:
            afip_caea = self.ensure_caea()

            FeDetReq = res.get('FeDetReq')[0]
            rdata = FeDetReq.pop('FECAEDetRequest')
            rdata.update({'CAEA': afip_caea.name})
            FeDetReq['FECAEADetRequest'] = rdata

            # * Code 1442: Si el punto de venta no es del tipo CONTINGENCIA para el CAEA en cuestion, no informar el campo CbteFchHsGen
            # 'CbteFchHsGen': self.date.strftime('%Y%m%d%H%M%S'),

            res.update({'FeDetReq': [FeDetReq]})
        return res

    def action_reprocess_caea_afip(self):
        invoices = self.filtered(lambda x: x.is_caea and x.state == 'posted' and x.l10n_ar_afip_result == 'R')
        if not invoices:
            raise UserError(_('There is not Reject CAEA Invoices ro reject'))

        invoices.l10n_ar_afip_result = False
        for inv in invoices:
            _logger.info("Reprocesar Factura CAEA fallida en AFIP %s", inv.display_name)
            afip_caea = inv.get_active_caea()
            afip_ws = afip_caea.get_afip_ws()
            return_info_all = []
            client, auth, transport = inv.company_id._l10n_ar_get_connection(afip_ws)._get_client(return_transport=True)
            return_info = inv._l10n_ar_do_afip_ws_request_caea(client, auth, transport)
            if return_info:
                return_info_all.append("<strong>%s</strong> %s" % (inv.name, return_info))
        if return_info_all:
            self.message_post(body='<p><b>' + _('AFIP Messages') +
                              '</b></p><p><ul><li>%s</li></ul></p>' % ('</li><li>'.join(return_info_all)))

    def _post(self, soft=True):
        """ Si estoy en modo contingencia entonces cambio el diario automaticamente al diairo debackup
        que este configurando en el diaro seleccionado por el usuario """
        for inv in self.filtered(lambda x: x.company_id.l10n_ar_contingency_mode and x.journal_id.l10n_ar_contingency_journal_id):
            inv.journal_id = inv.journal_id.l10n_ar_contingency_journal_id
            inv.message_post(body=("Debido a que esta en modo contigencia se cambio el diario seleccionado por el de contigencia relacionado"))

        return super()._post(soft=soft)

    def get_auth_mode(self):
        self.ensure_one()
        return 'CAEA' if self.is_caea else 'CAE'
