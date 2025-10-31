from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """
    Computar el tax_state de aquellos apuntes contables de impuestos que están en borrador. Si el asiento está en borrador entonces el tax_state debe ser False.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref["account.move.line"].search(
        [("parent_state", "=", "draft"), ("tax_state", "!=", False)]
    )._compute_tax_state()
