from odoo import _, models, fields
from odoo.exceptions import UserError

class AccountMove(models.Model):

    _inherit = 'account.move'

    l10n_ar_caea_id = fields.Many2one('l10n.ar.caea', copy=False)

    # TODO KZ pasar esto directamente a PR en Odoo oficial.
    l10n_ar_afip_result = fields.Selection(selection_add=[('R', 'Rejected in AFIP')])

    def _l10n_ar_do_afip_ws_request_cae(self):
        """ Extendemos el metodo original que termina haciendo lo de factura electronica para integrar lo de CAEA,
        dicho caso no reportamos a AFIP de manera inmediata """
        # TODO KZ hacer cuando implementemos contingencia or .journal_id.caea_journal_id
        cae_invoices = self.filtered(lambda x: x.l10n_ar_afip_ws == 'wsfe_caea' and not x.l10n_ar_afip_auth_code)
        validate_caea = self.env['account.move']
        validate_caea = cae_invoices._l10n_ar_do_afip_ws_request_caea()

        validated_cae = super(AccountMove, cae_invoices - self)._l10n_ar_do_afip_ws_request_cae()
        return validate_caea + validated_cae

    def _l10n_ar_do_afip_ws_request_caea(self):
        """ Valida las facturas utilizando CAEA """

        for inv in self:
            # TODO KZ oportunidad de mejora. mover el calculo del afip_caea previo al loop. desde alli ver los caea d
            # todas las compa;ias y hacer early return si no existe.
            afip_caea = inv.get_active_caea()
            if not afip_caea:
                raise UserError(_('Dont have CAEA Active'))
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
            ('date_from', '<=', self.date), ('date_to', '>=', self.date),])
        #     ('state', '=', 'active')
        # ], limit=1)

    def wsfe_get_cae_request(self, client=None):
        """ Extender el metodo que construye la data del request para agregar
        cosas que son necesarias con CAEA"""
        self.ensure_one()
        res = super().wsfe_get_cae_request(client=client)
        if self.l10n_ar_afip_ws == 'wsfe_caea':
            afip_caea = self.get_active_caea()
            if not afip_caea:
                raise UserError(_('Dont have CAEA Active'))
            data = res.pop('FeDetReq')
            data = data[0].pop('FECAEDetRequest')
            data.update({
                'CAEA': afip_caea.name,
                'CbteFchHsGen': self.date.strftime('%Y%m%d%H%M%S'),
            })
            res.update({'FeDetReq': [{'FECAEADetRequest': data}]})
        return res

    def _is_argentina_electronic_invoice(self):
        res = super()._is_argentina_electronic_invoice()
        res = res and 'caea' not in self.journal_id.l10n_ar_afip_ws
        return res
