# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nArArcaConnectionWizard(models.TransientModel):
    _name = "l10n_ar.arca.connection.wizard"
    _description = "ARCA Connection Setup Wizard"

    company_id = fields.Many2one(
        "res.company", string="Company", required=True, readonly=True, default=lambda self: self.env.company
    )

    l10n_ar_afip_ws_key_id = fields.Many2one(
        related="company_id.l10n_ar_afip_ws_key_id",
        string="Private Key",
        readonly=False,
        help="Upload your private key in PEM format. If you don't have one, "
        "it will be generated automatically when you create a certificate request.",
    )

    l10n_ar_afip_ws_crt_id = fields.Many2one(
        related="company_id.l10n_ar_afip_ws_crt_id",
        string="ARCA Certificate",
        readonly=False,
        help="Upload your ARCA certificate in PEM format obtained from the ARCA portal.",
    )

    connection_status_html = fields.Html(
        string="Connection Status",
        compute="_compute_connection_status_html",
        help="Shows the status of connections to different ARCA Web Services.",
    )

    has_valid_certificate = fields.Boolean(
        compute="_compute_has_valid_certificate", help="Indicates if a valid certificate is configured."
    )

    @api.depends("l10n_ar_afip_ws_crt_id")
    def _compute_has_valid_certificate(self):
        for wizard in self:
            wizard.has_valid_certificate = wizard.l10n_ar_afip_ws_crt_id and wizard.l10n_ar_afip_ws_crt_id.is_valid

    @api.depends("company_id")
    def _compute_connection_status_html(self):
        """Show status of configured web services connections"""
        for wizard in self:
            if not wizard.has_valid_certificate:
                wizard.connection_status_html = (
                    '<div class="alert alert-warning" role="alert"><strong>⚠️ %s</strong><br/>%s</div>'
                ) % (
                    _("No certificate configured"),
                    _("Please upload a valid private key and ARCA certificate to test connections."),
                )
                continue

            html = '<div class="mt-3"><h5>%s</h5><ul class="list-unstyled">' % _("Web Services Status:")

            # Check common web services
            ws_list = [
                ("wsfe", _("Electronic Invoice (WSFE)")),
                ("wsfex", _("Export Invoice (WSFEX)")),
                ("wsbfe", _("Electronic Fiscal Bond (WSBFE)")),
                ("ws_sr_constancia_inscripcion", _("ARCA Registration Certificate Inquiry Service (ex A5)")),
                ("wscdc", _("Invoices Verification (WSCDC)")),
                ("wsmtxca", _("Codificación de producto - RG2904 (WSMTXCA)")),
            ]

            for ws_code, ws_name in ws_list:
                try:
                    # Try to get or create connection
                    connection = wizard.company_id._l10n_ar_get_connection(ws_code)
                    if connection and connection.expiration_time > fields.Datetime.now():
                        status_class = "text-success"
                        status_icon = "✅"
                        status_text = _("Connected")
                    else:
                        status_class = "text-warning"
                        status_icon = "⚠️"
                        status_text = _("Token expired")
                except Exception:
                    status_class = "text-danger"
                    status_icon = "❌"
                    status_text = _("Not available")

                html += f'<li class="{status_class}"><strong>{status_icon} {ws_name}:</strong> {status_text}</li>'

            html += "</ul></div>"
            wizard.connection_status_html = html

    def action_test_connections(self):
        """Test connections to ARCA web services"""
        self.ensure_one()

        if not self.has_valid_certificate:
            raise UserError(
                _(
                    "Cannot test connections without a valid certificate.\n\n"
                    "Please upload both a private key and a valid ARCA certificate."
                )
            )

        # Force recompute of connection status
        self._compute_connection_status_html()

        # Show a notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connection Test"),
                "message": _("Connection status has been updated. Check the status below."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_save_and_close(self):
        """Save configuration and close wizard"""
        self.ensure_one()
        # Related fields are automatically saved
        return {"type": "ir.actions.act_window_close"}

    def action_open_documentation(self):
        """Open ARCA documentation in a new window"""
        return {
            "type": "ir.actions.act_url",
            "url": "https://www.adhoc.inc/odoo/knowledge/10634",
            "target": "new",
        }
