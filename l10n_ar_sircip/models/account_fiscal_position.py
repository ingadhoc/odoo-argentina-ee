##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command, api, fields, models
from odoo.exceptions import RedirectWarning


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    l10n_ar_sircip_warning = fields.Text(string="SIRCIP Warning", compute="_compute_l10n_ar_sircip_warning")

    @api.depends("company_id.l10n_ar_sircip_agent", "l10n_ar_tax_ids.default_tax_id", "l10n_ar_tax_ids.tax_type")
    def _compute_l10n_ar_sircip_warning(self):
        """Warn agent companies of perception positions lacking the SIRCIP line or holding adhered provinces."""
        for rec in self:
            messages = []
            perceptions = rec.l10n_ar_tax_ids.filtered(lambda x: x.tax_type == "perception")
            if rec.company_id.l10n_ar_sircip_agent and perceptions:
                sircip = perceptions.filtered(lambda x: x._l10n_ar_is_sircip())
                if not sircip:
                    messages.append(
                        self.env._(
                            "This fiscal position has perceptions but not the SIRCIP line: it is added when saving."
                        )
                    )
                adhered = (perceptions - sircip).default_tax_id.l10n_ar_state_id.filtered("l10n_ar_is_sircip")
                if adhered:
                    messages.append(
                        self.env._(
                            "Perceptions of provinces adhered to SIRCIP: %(states)s. They are now collected through "
                            "SIRCIP, remove those lines.",
                            states=", ".join(adhered.mapped("name")),
                        )
                    )
            rec.l10n_ar_sircip_warning = "\n".join(messages)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._l10n_ar_sircip_ensure_line()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "l10n_ar_tax_ids" in vals or "company_id" in vals:
            self._l10n_ar_sircip_ensure_line()
        return res

    @api.onchange("country_id")
    def _onchange_country_id(self):
        # EXTEND account
        """Keep the provinces preset by the SIRCIP "Find/Create fiscal position" button, which the country onchange
        would clear when the form applies the defaults."""
        states = self.state_ids
        res = super()._onchange_country_id()
        if self.env.context.get("l10n_ar_sircip_keep_states"):
            self.state_ids = states.filtered(lambda x: x.country_id == self.country_id)
        return res

    def _l10n_ar_sircip_fp_line(self):
        """SIRCIP line of the company's SIRCIP fiscal position, the model for the line of every other one."""
        self.ensure_one()
        fiscal_position = self.env.ref(
            "l10n_ar_sircip.fiscal_position_sircip_%s" % self.company_id.id, raise_if_not_found=False
        )
        if not fiscal_position:
            return self.env["account.fiscal.position.l10n_ar_tax"]
        return fiscal_position.l10n_ar_tax_ids.filtered(lambda x: x._l10n_ar_is_sircip())[:1]

    def _l10n_ar_sircip_ensure_line(self):
        """An invoice takes a single fiscal position: on agent companies, every one with perceptions also needs the
        SIRCIP line, or SIRCIP would not be perceived on its invoices."""
        for rec in self.filtered("company_id.l10n_ar_sircip_agent"):
            perceptions = rec.l10n_ar_tax_ids.filtered(lambda x: x.tax_type == "perception")
            sircip_line = rec._l10n_ar_sircip_fp_line()
            if perceptions and sircip_line and not perceptions.filtered(lambda x: x._l10n_ar_is_sircip()):
                sircip_line.copy({"fiscal_position_id": rec.id})

    def _l10n_ar_check_perceptions(self, partner, date):
        # EXTEND l10n_ar_tax
        """Digit 4 in the delivery province: that province perceives too, through its own line of the fiscal
        position. Without that line Odoo cannot know its aliquot, so the document is stopped."""
        res = super()._l10n_ar_check_perceptions(partner, date)
        for rec in self:
            perceptions = rec.l10n_ar_tax_ids.filtered(lambda x: x.tax_type == "perception")
            sircip_line = perceptions.filtered(lambda x: x._l10n_ar_is_sircip())[:1]
            if not sircip_line:
                continue
            partner = partner.commercial_partner_id
            delivery_id = self.env.context.get("l10n_ar_delivery_partner_id")
            delivery = self.env["res.partner"].browse(delivery_id) if delivery_id else partner
            state = delivery.state_id or partner.state_id
            data = sircip_line._sircip_get_padron_data(partner, date)
            if not data["in_padron"] or sircip_line._get_sircip_campo7_digit(data["campo7"], state) != 4:
                continue
            if not perceptions.filtered(lambda x: x.default_tax_id.l10n_ar_state_id == state):
                raise rec._l10n_ar_sircip_missing_province_error(partner, delivery, state)
        return res

    def _l10n_ar_sircip_missing_province_error(self, partner, delivery, state):
        """RedirectWarning to the fiscal positions that perceive the province, or to a new one ready to adjust."""
        self.ensure_one()
        message = self.env._(
            "According to the SIRCIP padron, %(partner)s also has the %(state)s perception (digit 4, delivery in "
            "%(state)s), but the fiscal position %(fiscal_position)s cannot compute it.\n\n"
            "To continue, use a fiscal position for deliveries in %(state)s with the %(state)s perception, with the "
            "aliquot loaded manually on the contact or obtained through its webservice or padron file.",
            partner=partner.display_name,
            state=state.name,
            fiscal_position=self.display_name,
        )
        candidates = self.search(
            [
                ("company_id", "=", self.company_id.id),
                ("l10n_ar_tax_ids.tax_type", "=", "perception"),
                ("l10n_ar_tax_ids.default_tax_id.l10n_ar_state_id", "=", state.id),
            ]
        )
        action = {
            "type": "ir.actions.act_window",
            "name": self.env._("Fiscal Positions"),
            "res_model": "account.fiscal.position",
            "views": [(False, "form")],
            "target": "current",
        }
        if candidates:
            for fiscal_position in candidates:
                message += "\n\n" + self.env._(
                    "%(fiscal_position)s perceives %(state)s but was not applied: %(reasons)s.",
                    fiscal_position=fiscal_position.display_name,
                    state=state.name,
                    reasons="; ".join(fiscal_position._l10n_ar_sircip_not_applied_reasons(partner, delivery, state)),
                )
            message += "\n\n" + self.env._("Fix it and select the fiscal position again on the document.")
            if len(candidates) == 1:
                action["res_id"] = candidates.id
            else:
                action.update(views=[(False, "list"), (False, "form")], domain=[("id", "in", candidates.ids)])
        else:
            action["context"] = self._l10n_ar_sircip_new_fp_defaults(partner, state)
        return RedirectWarning(message, action, self.env._("Find/Create fiscal position"))

    def _l10n_ar_sircip_not_applied_reasons(self, partner, delivery, state):
        """Why this fiscal position was not auto-detected for the partner and delivery."""
        self.ensure_one()
        reasons = []
        if not self.auto_apply:
            reasons.append(self.env._("it is not detected automatically"))
        if self.state_ids and state not in self.state_ids:
            reasons.append(self.env._("its provinces do not include %(state)s", state=state.name))
        responsibility = partner.l10n_ar_afip_responsibility_type_id
        if responsibility not in self.l10n_ar_afip_responsibility_type_ids:
            reasons.append(
                self.env._("it lacks the customer's AFIP responsibility (%(resp)s)", resp=responsibility.name or "-")
            )
        fixed = (delivery | partner).with_company(self.company_id).property_account_position_id[:1]
        if fixed and fixed != self:
            reasons.append(self.env._("the contact has the fiscal position %(fixed)s set", fixed=fixed.display_name))
        if not reasons:
            reasons.append(self.env._("the document fiscal position was set manually or before this one existed"))
        return reasons

    def _l10n_ar_sircip_new_fp_defaults(self, partner, state):
        """Defaults for a new fiscal position for deliveries in ``state``: its perception, manual, plus SIRCIP."""
        self.ensure_one()
        tax = (
            self.env["account.tax"]
            .with_context(active_test=False)
            .search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("type_tax_use", "=", "sale"),
                    ("amount_type", "=", "percent"),
                    ("l10n_ar_state_id", "=", state.id),
                    ("l10n_ar_sircip_record_type", "=", False),
                    ("tax_group_id.l10n_ar_tribute_afip_code", "=", "07"),
                ],
                limit=1,
            )
        )
        lines = [Command.create({"default_tax_id": tax.id, "tax_type": "perception"})] if tax else []
        sircip_line = self._l10n_ar_sircip_fp_line()
        if sircip_line:
            lines.append(Command.create(sircip_line.copy_data({"fiscal_position_id": False})[0]))
        responsibility = partner.l10n_ar_afip_responsibility_type_id
        return {
            "l10n_ar_sircip_keep_states": True,
            "default_name": self.env._("Perception %(state)s + SIRCIP", state=state.name),
            "default_company_id": self.company_id.id,
            "default_auto_apply": True,
            "default_country_id": state.country_id.id,
            "default_state_ids": [Command.set(state.ids)],
            "default_l10n_ar_afip_responsibility_type_ids": [Command.set(responsibility.ids)],
            "default_l10n_ar_tax_ids": lines,
        }

    def _l10n_ar_is_sircip_fp(self):
        self.ensure_one()
        return self == self.env.ref(
            "l10n_ar_sircip.fiscal_position_sircip_%s" % self.company_id.id, raise_if_not_found=False
        )

    def _l10n_ar_get_fp_tax_taxes(self, fp_tax, partner, company, date, tax_type, payment=None):
        # EXTEND l10n_ar_tax
        """Compute the SIRCIP line per invoice: it depends on the delivery province and may add a surcharge."""
        if tax_type == "perception" and fp_tax._l10n_ar_is_sircip():
            return fp_tax._sircip_get_taxes(partner, date)
        return super()._l10n_ar_get_fp_tax_taxes(fp_tax, partner, company, date, tax_type, payment=payment)
