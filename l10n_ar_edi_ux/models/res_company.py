import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    # TODO 20.0: drop this field, _l10n_ar_get_invoice_pdf_legend_company(),
    # _l10n_ar_migrate_withholding_legend(), its call from the post_init_hook, the
    # migration script and the views. Backport of odoo/enterprise#102032, which
    # l10n_ar_edi ships from 20.0 on with this very field name and selection keys, so
    # the stored value carries over on migration. Divergences from the upstream patch:
    # * upstream declares the field company_dependent=True; on res.company that keys
    #   the value by env.company instead of by the record, so the report would print
    #   the active company's legend instead of the one of the company that issued the
    #   invoice (and the country guard could be bypassed the same way). Stored per
    #   company record instead, branch fallback resolved when printing.
    # * l10n_ar_edi 19.0 already prints "Operation Subject to Withholding" out of its
    #   l10n_ar_show_withholding_legend boolean. This selector supersedes that boolean:
    #   its checkbox is removed from the settings view and its value is moved into this
    #   field, so the legend is configured in one place and printed once.
    l10n_ar_invoice_pdf_legend = fields.Selection(
        selection=[
            ("payment_on_informed_cbu", "Payment on Informed CBU"),
            ("operation_subject_to_withholding", "Operation Subject to Withholding"),
        ],
        string="Invoice PDF Legend",
        help="The selected legend is printed below the Document Type letter on the Invoice PDF of documents with"
        " letter A and M. Branches with no legend of their own print the one configured on the closest parent"
        " company.",
    )

    def _l10n_ar_get_invoice_pdf_legend_company(self):
        """Return the closest company of the parent chain (self included) that has an
        invoice PDF legend configured, so that branches fall back to their parent's
        legend the same way they fall back to its ARCA certificate
        (_l10n_ar_get_cert_ancestor). Returns an empty recordset when no company of the
        chain has one. TODO 20.0: drop."""
        self.ensure_one()
        company = self.sudo()
        while company and not company.l10n_ar_invoice_pdf_legend:
            company = company.parent_id
        return company

    @api.model
    def _l10n_ar_migrate_withholding_legend(self):
        """Move l10n_ar_edi's l10n_ar_show_withholding_legend into
        l10n_ar_invoice_pdf_legend, which supersedes it (see the field comment above).
        Called from the module post_init_hook and from its migration script so that
        companies already printing the withholding legend keep printing it, and it is
        printed only once. TODO 20.0: drop."""
        companies = self.sudo().search([("l10n_ar_show_withholding_legend", "=", True)])
        if not companies:
            return
        to_set = companies.filtered(lambda company: not company.l10n_ar_invoice_pdf_legend)
        to_set.l10n_ar_invoice_pdf_legend = "operation_subject_to_withholding"
        companies.l10n_ar_show_withholding_legend = False
        _logger.info(
            "Moved l10n_ar_show_withholding_legend into l10n_ar_invoice_pdf_legend on companies %s", companies.ids
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # When creating new branch, the env should be initializated with the same value
            # as the parent company to avoid issues
            if "l10n_ar_afip_ws_environment" not in vals and vals.get("parent_id"):
                parent = self.browse(vals["parent_id"])
                if parent.l10n_ar_afip_ws_environment:
                    vals["l10n_ar_afip_ws_environment"] = parent.l10n_ar_afip_ws_environment
        companies = super().create(vals_list)
        for company in companies:
            if company.country_id.code == "AR":
                key = f"l10n_ar_edi.{company.id}_foreign_currency_payment"
                self.env["ir.config_parameter"].sudo().set_param(key, "account")
        return companies

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
