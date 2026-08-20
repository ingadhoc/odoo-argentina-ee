##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountFiscalYear(models.Model):
    _inherit = "account.fiscal.year"

    company_id = fields.Many2one(default=lambda self: self.env.company.legal_entity_root_id)

    @api.constrains("date_from", "date_to", "company_id")
    def _check_dates(self):
        """Allow an explicit fiscal year on the head of a legal entity, not only on the root.

        Full replacement of ``account_accountant``'s constraint: the only thing that
        changes is the company test —its *"You cannot have a fiscal year on a child
        company"* becomes *"only the head of a legal entity"*— and Odoo offers no seam to
        replace that single check, since the date order and the overlap checks live in the
        same method.

        This is the sixth enforcement point of the fiscal year being delegated, and the
        one that would have left the whole thing half done: the explicit fiscal year wins
        over ``fiscalyear_last_day`` / ``fiscalyear_last_month``
        (``res_company.compute_fiscalyear_dates`` looks it up first), so a branch that
        heads its own legal entity could set the fields and still be unable to declare an
        irregular year. Keeping the ban for the rest of the entity is deliberate, and it
        is the same rule as the fields: the year belongs to the entity, so it is defined
        once, on its head, and every company of the entity reads it from there.

        The overlap check stays scoped to ``company_id``, which is equivalent to scoping
        it to the legal entity precisely because no other company of the entity can hold
        a fiscal year of its own.
        """
        for fy in self:
            if fy.date_to < fy.date_from:
                raise ValidationError(_("The ending date must not be prior to the starting date."))
            company = fy.company_id
            if company.legal_entity_root_id != company:
                raise ValidationError(
                    _(
                        "«%(company)s» is not the head of its legal entity —«%(head)s» is— so it cannot have "
                        "a fiscal year of its own: the fiscal year is defined once for the whole legal entity. "
                        "Create it on «%(head)s», or give «%(company)s» its own Tax ID if it really is a "
                        "different legal entity.",
                        company=company.display_name,
                        head=company.legal_entity_root_id.display_name,
                    )
                )
            # Copied verbatim from core, gap included: it does not catch a fiscal year
            # strictly contained in the one being saved. Fixing it is not this override's
            # business — the only thing that changes here is the company test above.
            overlapping = self.search_count(
                [
                    ("id", "!=", fy.id),
                    ("company_id", "=", company.id),
                    "|",
                    "|",
                    "&",
                    ("date_from", "<=", fy.date_from),
                    ("date_to", ">=", fy.date_from),
                    "&",
                    ("date_from", "<=", fy.date_to),
                    ("date_to", ">=", fy.date_to),
                    "&",
                    ("date_from", "<=", fy.date_from),
                    ("date_to", ">=", fy.date_to),
                ]
            )
            if overlapping:
                raise ValidationError(
                    _(
                        "You can not have an overlap between two fiscal years, please correct the start "
                        "and/or end dates of your fiscal years."
                    )
                )
