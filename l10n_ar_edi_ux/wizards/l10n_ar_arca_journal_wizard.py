# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class L10nArArcaJournalWizard(models.TransientModel):
    _name = "l10n_ar.arca.journal.wizard"
    _description = "ARCA Point of Sale Journals Generator"

    company_id = fields.Many2one(
        "res.company", string="Company", required=True, readonly=True, default=lambda self: self.env.company
    )

    pos_line_ids = fields.One2many("l10n_ar.arca.journal.wizard.line", "wizard_id", string="Points of Sale")

    has_points_of_sale = fields.Boolean(compute="_compute_has_points_of_sale")

    def action_create_manually(self):
        """Open the standard journal form to create a journal manually."""
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Journal"),
            "res_model": "account.journal",
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def action_open_wizard(self):
        """Return the action to open the ARCA journal wizard."""
        return self.env["ir.actions.act_window"]._for_xml_id("l10n_ar_edi_ux.action_l10n_ar_arca_journal_wizard")

    @api.depends("pos_line_ids")
    def _compute_has_points_of_sale(self):
        for wizard in self:
            wizard.has_points_of_sale = bool(wizard.pos_line_ids)

    def action_fetch_points_of_sale(self):
        """Fetch points of sale from ARCA web services"""
        self.ensure_one()

        if not self.company_id.l10n_ar_afip_ws_crt_id or not self.company_id.l10n_ar_afip_ws_crt_id.is_valid:
            raise UserError(
                _(
                    "No valid ARCA certificate found.\n\n"
                    "Please configure your certificate in the ARCA Connection Setup before fetching points of sale."
                )
            )

        # Clear existing lines
        self.pos_line_ids.unlink()

        # Get points of sale for each web service
        pos_data_list = []
        ws_types = [
            ("wsfe", "RAW_MAW", _("Electronic Invoice")),
            ("wsfex", "FEEWS", _("Export Invoice")),
            ("wsbfe", "BFEWS", _("Electronic Fiscal Bond")),
        ]

        for ws_code, pos_system, ws_name in ws_types:
            try:
                connection = self.company_id._l10n_ar_get_connection(ws_code)
                client, auth = connection._get_client()

                # Call corresponding service method
                if ws_code == "wsfe":
                    response = client.service.FEParamGetPtosVenta(auth)
                    if hasattr(response, "ResultGet") and hasattr(response.ResultGet, "PtoVenta"):
                        for pos in response.ResultGet.PtoVenta:
                            pos_data_list.append(
                                {
                                    "wizard_id": self.id,
                                    "afip_ws": ws_code,
                                    "afip_ws_name": ws_name,
                                    "pos_number": pos.Nro,
                                    "pos_system": pos_system,
                                    "name": _("Sales %s %05d") % (ws_name, pos.Nro),
                                    "to_create": True,
                                }
                            )
                elif ws_code == "wsfex":
                    response = client.service.FEXGetPARAM_PtoVenta(auth)
                    if hasattr(response, "FEXResultGet") and hasattr(response.FEXResultGet, "PtoVenta"):
                        for pos in response.FEXResultGet.PtoVenta:
                            pos_data_list.append(
                                {
                                    "wizard_id": self.id,
                                    "afip_ws": ws_code,
                                    "afip_ws_name": ws_name,
                                    "pos_number": pos.Pto_venta,
                                    "pos_system": pos_system,
                                    "name": _("Sales %s %05d") % (ws_name, pos.Pto_venta),
                                    "to_create": True,
                                }
                            )
                # Note: wsbfe doesn't have a method to get POS list, skip it

            except Exception as e:
                _logger.warning("Could not fetch points of sale for %s: %s", ws_code, e)
                continue

        if not pos_data_list:
            raise UserError(
                _(
                    "No points of sale found in ARCA.\n\n"
                    "This could mean:\n"
                    "- You don't have any points of sale configured in ARCA\n"
                    "- The connection failed\n"
                    "- You are in testing mode (testing mode doesn't support this query)\n\n"
                    "Please check your ARCA configuration."
                )
            )

        # Create lines
        self.env["l10n_ar.arca.journal.wizard.line"].create(pos_data_list)

        return self.env["ir.actions.act_window"]._for_xml_id("l10n_ar_edi_ux.action_l10n_ar_arca_journal_wizard") | {
            "res_id": self.id
        }

    def action_create_journals(self):
        """Create journals for selected points of sale"""
        self.ensure_one()

        lines_to_create = self.pos_line_ids.filtered(lambda line: line.to_create)

        if not lines_to_create:
            raise UserError(_("Please select at least one point of sale to create."))

        created_journals = self.env["account.journal"]

        company_ids = {line.branch_id.id or self.company_id.id for line in lines_to_create}
        pos_numbers = lines_to_create.mapped("pos_number")
        existing_journals = self.env["account.journal"].search(
            [
                ("company_id", "in", list(company_ids)),
                ("l10n_ar_afip_pos_number", "in", pos_numbers),
                ("type", "=", "sale"),
            ]
        )
        existing_map = {(j.company_id.id, j.l10n_ar_afip_pos_number): j for j in existing_journals}

        for line in lines_to_create:
            company_id = line.branch_id.id or self.company_id.id
            existing = existing_map.get((company_id, line.pos_number))

            if existing:
                line.error_message = _("Journal already exists: %s") % existing.name
                continue

            # Prepare journal values
            vals = {
                "name": line.name,
                "type": "sale",
                "code": f"{line.pos_number:05d}",
                "company_id": line.branch_id.id or self.company_id.id,
                "l10n_latam_use_documents": True,
                "l10n_ar_afip_pos_number": line.pos_number,
                "l10n_ar_afip_pos_system": line.pos_system,
                "l10n_ar_afip_pos_partner_id": (line.branch_id or self.company_id).partner_id.id,
                "shared_to_branches": line.shared_to_branches,
            }

            try:
                with self.env.cr.savepoint():
                    journal = self.env["account.journal"].create(vals)
                created_journals |= journal
                line.error_message = False
            except Exception as e:
                _logger.warning("Could not create journal for POS %s: %s", line.pos_number, e)
                line.error_message = str(e)

        # Show created journals
        if created_journals:
            return {
                "type": "ir.actions.act_window",
                "name": _("Created Journals"),
                "res_model": "account.journal",
                "view_mode": "list,form",
                "domain": [("id", "in", created_journals.ids)],
                "target": "current",
            }

        # No journals created — reopen wizard showing error messages
        return self.env["ir.actions.act_window"]._for_xml_id("l10n_ar_edi_ux.action_l10n_ar_arca_journal_wizard") | {
            "res_id": self.id
        }
