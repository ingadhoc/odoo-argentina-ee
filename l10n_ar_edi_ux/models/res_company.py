from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    # TODO 20.0: drop this field, its compute and its views. It is a backport of
    # odoo/enterprise#102032, which l10n_ar_edi already ships in 20.0. Copied from
    # upstream except for its company_dependent=True: on res.company that keys the
    # value by env.company instead of by the record, so the report would print the
    # active company's legend instead of the one of the company that issued the
    # invoice.
    l10n_ar_invoice_pdf_legend = fields.Selection(
        selection=[
            ("payment_on_informed_cbu", "Payment on Informed CBU"),
            ("operation_subject_to_withholding", "Operation Subject to Withholding"),
        ],
        compute="_compute_l10n_ar_invoice_pdf_legend",
        store=True,
        readonly=False,
        help="Selected legend value will be added below the Document Type letter on the Invoice PDF.",
    )

    @api.depends("country_code")
    def _compute_l10n_ar_invoice_pdf_legend(self):
        for company in self:
            if company.country_code != "AR":
                company.l10n_ar_invoice_pdf_legend = False

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
