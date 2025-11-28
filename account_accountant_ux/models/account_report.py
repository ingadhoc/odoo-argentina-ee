##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class AccountReport(models.Model):
    _inherit = "account.report"

    require_custom_filter = fields.Boolean(
        help="If enabled, the report will not load data unless a custom filter or partner filter is applied.",
        default=False,
    )

    def _get_options_domain(self, options, date_scope):
        """Override to add a dummy domain if custom filter is required and no filters are applied."""
        domain = super()._get_options_domain(options, date_scope)

        if self.require_custom_filter:
            has_partner_filter = options.get("partner_ids") and len(options.get("partner_ids", [])) > 0
            has_aml_filter = False
            has_partner_categories_filter = options.get("selected_partner_categories")

            aml_ir_filters = options.get("aml_ir_filters", [])
            if aml_ir_filters:
                has_aml_filter = any(f.get("selected") for f in aml_ir_filters)

            if not has_partner_filter and not has_aml_filter and not has_partner_categories_filter:
                domain = [("id", "=", False)]

        return domain
