from odoo import models


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    def execute_action(self, options, params=None):
        """ Para liquidacioón de impuestos desde reportes agregamos en contexto
        * from_report_id: para saber desde que reporte vamos
        * context: con las options convertidas a context

        nativamente odoo solo pasa las options si el tipo de accion es url,
        pero preferimos hacer accion tipo ventana porque es mas facil
        implementar el que se abra la ventana, eso si, es necesario
        mandar las options para saber los filtros porque odoo no las manda en
        este caso
        Podriamos evitar este maneje si usamos action tipo url pero que luego
        devuelva la accion de ventana
        """
        action_id = int(params.get('actionId'))
        action = self.env['ir.actions.actions'].browse([action_id])

        action_read = super(AccountReport, self).execute_action(
            options, params=params)

        # necesitamos comparar los .id porque en realidad son dos modelos !=
        if action.type == 'ir.actions.act_window' and \
                self.env['ir.actions.act_window'].browse(action.id).binding_model_id.model \
                == 'account.financial.html.report.line':

            context = action_read.get('context') or {}
            context['from_report_id'] = self.id
            # convertimos las options a un context que mandamos con clave
            # context dentro del context para que sea interpretado por
            # report_move_lines_action
            ctx = self._set_context(options)
            # en reportes que no usan rango de fechas no hay seteada date_from
            # y eso hace que report_move_lines_action no evalue dominio.
            # reportes sin from date deberian evaluar desde siempre
            # (cuentas patrimoniales) asique ponemos una fecha bien al inicio
            if 'date_to' in ctx:
                context['default_date'] = ctx['date_to']
            # TODO we need a refactor of all this. Provably, to get the dates domain, the bet way would be
            # calling _get_options_date_domain or maybe _get_options_domain with the options but later when used
            if options.get('date', {}).get('mode') == 'single':
                ctx['date_from'] = '1900-01-01'
            context['context'] = ctx

            action_read['context'] = context
        return action_read
