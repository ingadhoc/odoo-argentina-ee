from odoo import models, api


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    # Do not duplicate move_name (this should go in odoo standard)
    @api.model
    def _format_aml_name(self, line_name, move_ref, move_name):
        ''' Format the display of an account.move.line record. As its very costly to fetch the account.move.line
        records, only line_name, move_ref, move_name are passed as parameters to deal with sql-queries more easily.

        :param line_name:   The name of the account.move.line record.
        :param move_ref:    The reference of the account.move record.
        :param move_name:   The name of the account.move record.
        :return:            The formatted name of the account.move.line record.
        '''
        names = []
        if move_name != '/':
            names.append(move_name)
        if move_ref and move_ref != '/':
            names.append(move_ref)
        if line_name and line_name != '/' and line_name != move_name:
            names.append(line_name)
        name = '-'.join(names)
        # TODO: check if no_format is still needed
        if len(name) > 35 and not self.env.context.get('no_format'):
            name = name[:32] + "..."
        return name
