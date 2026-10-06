##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    vat = fields.Char(
        help="Tax ID of the company. If the company is not subject to tax (for example, an auxiliary parent "
        "company), leave it empty: a company without Tax ID is its own legal entity and is left out of the "
        "returns of its parent.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._set_legal_entity_opening_date()
        return companies

    def write(self, vals):
        res = super().write(vals)
        if "vat" in vals and (ar_companies := self.filtered(lambda c: c.account_fiscal_country_id.code == "AR")):
            dated = ar_companies._set_legal_entity_opening_date()
            # Core refreshes the returns only on a few fields (``account_reports``
            # ``res.company.write``), and the Tax ID is not one of them, although it decides
            # which company of the tree files. Setting the opening date already refreshed.
            roots = (ar_companies.root_id - dated.root_id).filtered("account_opening_date")
            if roots:
                self.env["account.return.type"]._generate_or_refresh_all_returns(roots)
        return res

    def _set_legal_entity_opening_date(self):
        """Give an opening date to the Argentinian branches that head another legal entity.

        Enterprise creates returns for a branch with another Tax ID only when that branch
        has its own ``account_opening_date`` (``_try_create_returns_for_fiscal_year``), and
        branches are created without one. Nothing warns about it when standing on the
        parent, so the branch is left without returns. The default is the opening date of
        the closest ancestor, and it can be changed afterwards.

        :return: the companies that got an opening date. Writing it already refreshes the
            returns of their tree.
        """
        heads = (
            self.sudo()
            .search([("id", "child_of", self.ids)])
            .filtered(
                lambda c: c.parent_id
                and c.account_fiscal_country_id.code == "AR"
                and not c.account_opening_date
                and c.legal_entity_root_id == c
                and c._normalized_vat()
            )
        )
        dated = self.browse()
        for company in heads:
            opening_date = next(
                (
                    parent.account_opening_date
                    for parent in reversed(company.parent_ids - company)
                    if parent.account_opening_date
                ),
                False,
            )
            if opening_date:
                company.account_opening_date = opening_date
                dated |= company
        return dated
