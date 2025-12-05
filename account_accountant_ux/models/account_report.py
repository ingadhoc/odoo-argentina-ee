##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models
from odoo.fields import Domain


class AccountReport(models.Model):
    _inherit = "account.report"

    require_custom_filter = fields.Boolean(
        help="If enabled, the report will not load data unless a custom filter or partner filter is applied.",
        default=False,
    )
    filter_show_all_custom = fields.Boolean(
        string="Show All",
        readonly=False,
        store=True,
    )

    def _init_options_show_all_custom(self, options, previous_options):
        """Initialize the show_all_custom option."""
        if self.filter_show_all_custom and self.require_custom_filter:
            options["show_all_custom"] = previous_options.get("show_all_custom", False)
        else:
            options["show_all_custom"] = False

    def _init_options_filters(self, options, previous_options):
        """Override to add the require_custom_filter flag to options."""
        super()._init_options_filters(options, previous_options)
        # Only show the filter if require_custom_filter is enabled
        options["filters"]["show_all_custom"] = self.filter_show_all_custom and self.require_custom_filter

    def _get_options_domain(self, options, date_scope):
        """Override to add a dummy domain if custom filter is required and no filters are applied."""
        domain = super()._get_options_domain(options, date_scope)

        if self.require_custom_filter:
            # Si el filtro "Mostrar todo" está activo, no aplicar restricción
            if options.get("show_all_custom"):
                return domain

            has_partner_filter = options.get("partner_ids") and len(options.get("partner_ids", [])) > 0
            has_aml_filter = False
            has_partner_categories_filter = options.get("selected_partner_categories")

            aml_ir_filters = options.get("aml_ir_filters", [])
            if aml_ir_filters:
                has_aml_filter = any(f.get("selected") for f in aml_ir_filters)

            if not has_partner_filter and not has_aml_filter and not has_partner_categories_filter:
                domain = Domain("id", "=", False)

        return domain
