from odoo import models


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    def _format_aml_name(self, aml):
        """ Use display_name instead of name """
        name = '-'.join(
            (aml.move_id.display_name not in ['', '/'] and [aml.move_id.display_name] or []) +
            (aml.ref not in ['', '/', False] and [aml.ref] or []) +
            ([aml.name] if aml.name and aml.name not in ['', '/'] else [])
        )
        if len(name) > 35 and not self.env.context.get('no_format'):
            name = name[:32] + "..."
        return name
