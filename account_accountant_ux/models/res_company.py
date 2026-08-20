##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    block_intercompany_conciliation = fields.Boolean(
        string="Bloquear conciliación entre diferentes compañías",
        help="Si está activado, se bloqueará la conciliación entre movimientos "
        "de diferentes compañías ya sean entre empresas o sucursales.",
        default=False,
    )

    def _validate_locks(self, values):
        # Bypass controlado por parámetro de sistema 'account.bypass_lock_date_validation'.
        # Útil para correcciones puntuales de datos (ej: desbloquear hard_lock_date).
        # Por defecto False; activar con precaución y desactivar inmediatamente después.
        bypass = (
            self.env["ir.config_parameter"].sudo().get_param("account.bypass_lock_date_validation", default="False")
        )
        if bypass == "True":
            return
        return super()._validate_locks(values)

    def _get_branches_with_same_vat(self, accessible_only=False):
        """Answer "which branches are the same legal entity" with our own criterion.

        This is the seam of the whole thing. Enterprise resolves it natively by treating
        an empty Tax ID as the closest parent's one, so an auxiliary company with no Tax
        ID ends up inside the parent's group — and that is exactly the case we need to
        keep out of the parent's VAT book and returns.

        Overriding here reaches every consumer for free, because they all call this
        method: the tax reports that ignore the company selector and consolidate by Tax
        ID (``account_report._init_options_multi_company``), the export button gate
        (``enable_export_buttons_for_common_vat_in_branches``), whether a return may
        exist at all (``account_return._can_return_exist``) and the AR daily book Odoo
        wrote upstream.

        The criterion itself lives in ``account_ux``, where Enterprise is not a
        dependency, because it is also needed for record rules of records shared to
        branches. The bridge lives here, and not in ``account_multicompany_ux``, so that
        module keeps no dependency on Enterprise at all.

        There is a second divergence besides the empty Tax ID, and it is deliberate:
        Enterprise's traversal is **directional** —standing on a company it answers with
        that company and the branches below it— while ours answers with the whole legal
        entity, ancestors included. What is filed from a branch belongs to the entity, not
        to the branch. It matters most in ``account_return._can_return_exist``, which
        calls the shallowest company of the group the "main branch": with the ancestors in,
        a branch sharing its parent's Tax ID is no longer its own main branch, so the
        return belongs to the head of the entity and is filed there. Both halves of the
        divergence are pinned in ``tests/test_legal_entity_branches.py``.
        """
        return self._get_legal_entity_companies(accessible_only=accessible_only)
