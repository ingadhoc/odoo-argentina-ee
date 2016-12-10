# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from openupgradelib import openupgrade
from openupgradelib.openupgrade import logged_query

column_copies = {
    'infrastructure_database': [
        ('contract_id', None, None),
    ],
}


@openupgrade.migrate()
def migrate(cr, version):
    # delete_views(cr)
    openupgrade.copy_columns(cr, column_copies)
    logged_query(cr, """
        UPDATE infrastructure_database set contract_id = Null
    """)
