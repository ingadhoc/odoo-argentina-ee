##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    def _get_legal_entity_delegated_field_names(self):
        # Returns are filed by the head of the legal entity, so its branches share its opening date.
        return super()._get_legal_entity_delegated_field_names() + ["account_opening_date"]

    def write(self, vals):
        if "account_opening_date" not in vals:
            return super().write(vals)
        # account_reports reads the opening date as a singleton when it changes, and account_ux
        # propagates it to all the branches of the legal entity in a single write. The head of the
        # legal entity already refreshes the returns, so its branches skip it.
        # Parents first: each branch is checked against its parent's date.
        for company in self.sorted(lambda company: (company.parent_path or "").count("/")):
            if company.legal_entity_root_id != company:
                company._l10n_ar_check_opening_date_is_set_on_head(vals["account_opening_date"])
                company = company.with_context(l10n_ar_skip_returns_refresh=True)
            super(ResCompany, company).write(vals)
        return True

    def _l10n_ar_check_opening_date_is_set_on_head(self, opening_date):
        """A branch with the Tax ID of its head cannot have its own opening date: explain where to set it."""
        self.ensure_one()
        head = self.legal_entity_root_id
        if fields.Date.to_date(opening_date) == head.account_opening_date:
            return
        raise ValidationError(
            self.env._(
                "The company '%(company)s' has the same Tax ID as its parent '%(parent)s'. "
                "Please switch to the company '%(parent)s' and set the opening date there. "
                "'%(company)s' will inherit the opening date from '%(parent)s'.",
                company=self.display_name,
                parent=head.display_name,
            )
        )

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields=allfields, attributes=attributes)
        vat = res.get("vat")
        if vat is not None and (not attributes or "help" in attributes):
            # Append to the native help instead of replacing it
            ar_help = self.env._("For Argentina: if the company is not subject to tax, leave the Tax ID empty.")
            vat["help"] = f"{vat['help']}\n\n{ar_help}" if vat.get("help") else ar_help
        return res
