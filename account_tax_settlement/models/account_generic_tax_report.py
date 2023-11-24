from odoo import models


class GenericTaxReportCustomHandler(models.AbstractModel):

    _inherit = 'account.generic.tax.report.handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        """ Se borra boton tax closing ('Cierre de impuestos') en tax report ('Reporte de impuestos'). """
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        for x in (options['buttons']):
            if x.get('action') == 'action_periodic_vat_entries':
                options['buttons'].remove(x)
