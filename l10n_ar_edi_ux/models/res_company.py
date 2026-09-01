import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Options of l10n_ar_invoice_pdf_legend_ux: {value: (label of the selection, wording
# printed on the invoice PDF)}. The wording of ARCA RG 5762/2025 is kept here, out of the
# report arch, so that it is not exported as a translatable term of the view: the legend
# has to be printed in Spanish whatever the language the report is rendered in and
# whatever translations are loaded for this module. The selection of the field is built
# from this same dict so that an option can not be added without its wording -- it would
# be configurable in the UI and print nothing. TODO 20.0: drop.
L10N_AR_INVOICE_PDF_LEGENDS = {
    "payment_on_informed_cbu": ("Payment on Informed CBU", "Pago en CBU informado"),
    "operation_subject_to_withholding": ("Operation Subject to Withholding", "Operación sujeta a retención"),
}


class ResCompany(models.Model):
    _inherit = "res.company"

    # TODO 20.0: MANDATORY on the 19.0 -> 20.0 update, not an optional cleanup. Drop
    # this field, L10N_AR_INVOICE_PDF_LEGENDS, _l10n_ar_get_invoice_pdf_legend_text(),
    # _l10n_ar_migrate_withholding_legend(), its call from the post_init_hook, the
    # migration script, _l10n_ar_is_argentinian(), the country guard in create()/write()
    # and the views, and move
    # the stored value into l10n_ar_edi's own l10n_ar_invoice_pdf_legend (same selection
    # keys) with a pre-migration script. Kept as is, the module does not even install on
    # 20.0: it hard-depends on internals that 20.0 removes, and every one of them fails
    # the module load with "Element cannot be located in parent view" instead of
    # degrading -- the l10n_ar_show_withholding_legend checkbox this view replaces, the
    # l10n_ar_edi.custom_header_inherit template this report inherits, and the block it
    # replaces inside it.
    # Backport of odoo/enterprise#102032, which l10n_ar_edi ships from 20.0 on.
    # Divergences from the upstream patch:
    # * the field is NOT named l10n_ar_invoice_pdf_legend like upstream's on purpose:
    #   upstream declares it company_dependent=True, which stores it in a jsonb column,
    #   so sharing the name would make the 20.0 update run
    #   "ALTER COLUMN ... TYPE jsonb USING l10n_ar_invoice_pdf_legend::jsonb" over our
    #   varchar values and fail with a DataError.
    # * upstream's company_dependent=True is not used either: on res.company it keys the
    #   value by env.company instead of by the record, so the report would print the
    #   legend of the active company instead of the one of the company that issued the
    #   invoice (and the country guard could be bypassed the same way). Stored per
    #   company record instead, like the l10n_ar_edi boolean it replaces.
    # * l10n_ar_edi 19.0 already prints "Operation Subject to Withholding" out of its
    #   l10n_ar_show_withholding_legend boolean. This selector supersedes it: the
    #   checkbox is dropped from the settings, the report block is replaced by this
    #   module's one, and the value of the boolean is copied into this field. The
    #   boolean itself is left untouched -- printing once is guaranteed by replacing the
    #   report block, not by the value of the data, so there is no reason to destroy the
    #   only record of the previous configuration (it is what restores the old behaviour
    #   if this module is uninstalled or this backport reverted).
    l10n_ar_invoice_pdf_legend_ux = fields.Selection(
        selection=[(value, labels[0]) for value, labels in L10N_AR_INVOICE_PDF_LEGENDS.items()],
        string="Invoice PDF Legend",
        help="The selected legend is printed below the Document Type letter on the Invoice PDF of documents with"
        " letter A and M. It is set per company: branches do not inherit the legend of their parent company, they"
        " only start from its value when they are created. It supersedes the l10n_ar_edi 'Add Withholding Legend to"
        " Invoice PDF' setting, whose value is left as it was and stops being read, so uninstalling this module"
        " restores it.",
    )

    def _l10n_ar_get_invoice_pdf_legend_text(self):
        """Return the wording to print for the legend configured on this company, or an
        empty string when it has none. TODO 20.0: drop."""
        self.ensure_one()
        legend = self.l10n_ar_invoice_pdf_legend_ux
        if legend and legend not in L10N_AR_INVOICE_PDF_LEGENDS:
            _logger.warning(
                "No wording defined for invoice PDF legend %r of company %s, nothing is printed", legend, self.id
            )
            return ""
        return L10N_AR_INVOICE_PDF_LEGENDS[legend][1] if legend else ""

    @api.model
    def _l10n_ar_migrate_withholding_legend(self):
        """Copy l10n_ar_edi's l10n_ar_show_withholding_legend into
        l10n_ar_invoice_pdf_legend_ux, which supersedes it (see the field comment above),
        so that companies already printing the withholding legend keep printing it and no
        other company starts printing it. The boolean is left as it is, so uninstalling
        this module restores the previous behaviour. Companies that already have a legend
        of their own are not touched, which also makes this idempotent. Called from the
        module post_init_hook and from its migration script. TODO 20.0: drop."""
        companies = self.sudo().with_context(active_test=False).search([("l10n_ar_show_withholding_legend", "=", True)])
        to_set = companies.filtered(
            lambda company: not company.l10n_ar_invoice_pdf_legend_ux and company._l10n_ar_is_argentinian()
        )
        if not to_set:
            return
        to_set.l10n_ar_invoice_pdf_legend_ux = "operation_subject_to_withholding"
        _logger.info(
            "Copied l10n_ar_show_withholding_legend into l10n_ar_invoice_pdf_legend_ux on companies %s", to_set.ids
        )

    def _l10n_ar_is_argentinian(self):
        """Whether this company operates in Argentina, walking up the parent chain when it
        has no country of its own: res.company.country_id is not stored (it is a
        compute/inverse over partner_id) and it is not delegated from the parent company
        either (see _get_company_root_delegated_field_names), so a branch created from the
        Branches tab of its parent has no country while it does operate as an Argentinian
        branch. TODO 20.0: drop."""
        self.ensure_one()
        company = self.sudo()
        while company and not company.country_code:
            company = company.parent_id
        return company.country_code == "AR"

    def _l10n_ar_clean_invoice_pdf_legend(self):
        """Drop the legend of the companies that do not operate in Argentina, the way
        upstream's compute does it on country_code. Done on create()/write() instead of
        with a compute because a compute that does not assign on Argentinian companies
        leaves the field to False in cache while the database keeps the stored value.
        TODO 20.0: drop."""
        self.filtered(
            lambda company: company.l10n_ar_invoice_pdf_legend_ux and not company._l10n_ar_is_argentinian()
        ).l10n_ar_invoice_pdf_legend_ux = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # When creating new branch, the env should be initializated with the same value
            # as the parent company to avoid issues
            if vals.get("parent_id"):
                parent = self.browse(vals["parent_id"])
                if "l10n_ar_afip_ws_environment" not in vals and parent.l10n_ar_afip_ws_environment:
                    vals["l10n_ar_afip_ws_environment"] = parent.l10n_ar_afip_ws_environment
                # TODO 20.0: drop along with the rest of the odoo/enterprise#102032
                # backport. The legend is not inherited when printing (see the field
                # comment), so a new branch starts from the parent's one.
                if "l10n_ar_invoice_pdf_legend_ux" not in vals and parent.l10n_ar_invoice_pdf_legend_ux:
                    vals["l10n_ar_invoice_pdf_legend_ux"] = parent.l10n_ar_invoice_pdf_legend_ux
        companies = super().create(vals_list)
        # TODO 20.0: drop along with the rest of the odoo/enterprise#102032 backport.
        companies._l10n_ar_clean_invoice_pdf_legend()
        for company in companies:
            if company.country_id.code == "AR":
                key = f"l10n_ar_edi.{company.id}_foreign_currency_payment"
                self.env["ir.config_parameter"].sudo().set_param(key, "account")
        return companies

    def write(self, vals):
        res = super().write(vals)
        # TODO 20.0: drop along with the rest of the odoo/enterprise#102032 backport.
        if "country_id" in vals:
            self._l10n_ar_clean_invoice_pdf_legend()
        return res

    def _l10n_ar_get_cert_ancestor(self):
        """Return the nearest ancestor that shares the same CUIT and has an ARCA
        certificate configured. Walks the full parent chain so that multi-level
        branch hierarchies are supported (e.g. grandchild → child → parent with
        cert).  Returns an empty recordset when no such ancestor exists.

        Uses partner_id.l10n_ar_vat (normalized via stdnum.ar.cuit.compact) for
        comparison so that different VAT formats (with/without dashes) are handled
        correctly."""
        self.ensure_one()
        my_vat = self.partner_id.l10n_ar_vat
        if not my_vat:
            return self.env["res.company"]
        ancestor = self.parent_id.sudo()
        while ancestor:
            if ancestor.partner_id.l10n_ar_vat == my_vat and ancestor.l10n_ar_afip_ws_crt_id:
                return ancestor
            ancestor = ancestor.parent_id
        return self.env["res.company"]

    def _l10n_ar_get_connection(self, afip_ws):
        # EXTEND l10n_ar_edi
        """We adapt this method to be able to share connections between branches
        and parents that share the same CUIT number.

        Supports multi-level hierarchies: if this company has no certificate it
        walks up the parent chain (via _l10n_ar_get_cert_ancestor) to find the
        first ancestor with the same CUIT that owns a certificate, then
        delegates the connection lookup to that ancestor.

        If no ancestor with a matching cert is found, raises a clear UserError.

        A missing CUIT on a branch that has a parent is detected early and
        reported with a clear message."""
        self.ensure_one()
        if not self.sudo().l10n_ar_afip_ws_crt_id and self.parent_id:
            if not self.vat:
                raise UserError(
                    _(
                        'Company "%s" has no CUIT configured. A CUIT is required to get an ARCA connection.',
                        self.name,
                    )
                )
            cert_ancestor = self._l10n_ar_get_cert_ancestor()
            if cert_ancestor:
                return super(ResCompany, cert_ancestor)._l10n_ar_get_connection(afip_ws)
            raise UserError(
                _(
                    'Company "%s" has no ARCA certificate and no ancestor sharing the same CUIT '
                    "was found. Please configure a certificate in the accounting settings.",
                    self.name,
                )
            )

        return super()._l10n_ar_get_connection(afip_ws)

    def _check_match_between_certificate_and_company(self):
        """Check if the CUIT of the company match with the one in the certificate:
        - if match, continue with the normal flow to get token data
        - if not match, raise an error showing the difference between the
        certificate and company CUIT so the user can fix the configurations.

        Example: certificate.l10n_ar_subject_serial_number store = "CUIT 30111111118" """
        self.ensure_one()
        certificate_sudo = self.sudo().l10n_ar_afip_ws_crt_id
        if certificate_sudo and (
            not self.partner_id.l10n_ar_vat
            or certificate_sudo.l10n_ar_subject_serial_number != "CUIT %s" % self.partner_id.vat
        ):
            raise UserError(
                _(
                    "Certificate CUIT differ from Company's doc type and number. You can only use the ARCA certificate"
                    " if it matches\n * certificate %s\n * company %s %s"
                )
                % (
                    certificate_sudo.l10n_ar_subject_serial_number,
                    self.partner_id.l10n_latam_identification_type_id.name,
                    self.partner_id.vat,
                )
            )
