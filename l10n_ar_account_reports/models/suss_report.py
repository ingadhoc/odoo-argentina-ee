from odoo import models

from .helpers import get_suss_tax_group_ids


class L10n_ArSussReportHandler(models.AbstractModel):
    _name = "l10n_ar.suss.report.handler"
    _inherit = ["account.tax.report.handler"]
    _description = "Argentinian SUSS Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # Report domains are static, so the SUSS tax groups (one per company) are filtered here
        options.setdefault("forced_domain", []).append(
            ("tax_line_id.tax_group_id", "in", get_suss_tax_group_ids(self.env))
        )
