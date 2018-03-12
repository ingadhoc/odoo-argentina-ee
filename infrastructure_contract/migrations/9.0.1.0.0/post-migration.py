# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from openupgradelib import openupgrade
from openupgradelib.openupgrade import logged_query


@openupgrade.migrate()
def migrate(cr, version):
    # cr = env.cr

    analytic_account_column = openupgrade.get_legacy_name('contract_id')
    print 'bbbbbbbbb'
    print 'bbbbbbbbb'
    print 'bbbbbbbbb', analytic_account_column
    from psycopg2.extensions import AsIs
    logged_query(cr, """
        SELECT id, %s FROM infrastructure_database WHERE %s is not null
    """, (AsIs(analytic_account_column), AsIs(analytic_account_column)))

    print 'ccccccccc'
    print 'ccccccccc'
    recs = cr.fetchall()
    print 'ccccccccc', recs
    for database_id, analytic_account_id in recs:
        print 'analytic_account_id', analytic_account_id
        print 'database_id', database_id
        logged_query(cr, """
            SELECT id FROM sale_subscription WHERE analytic_account_id = %s
        """, (analytic_account_id,))
        print 'dddddddddd'
        print 'dddddddddd'
        print 'dddddddddd'
        read = cr.fetchall()
        # contract_recs = cr.fetchone()
        contract_id = read and read[0] or False
        print 'contract_id', contract_id
        if contract_id:
            logged_query(cr, """
                UPDATE infrastructure_database set contract_id = %s
                WHERE id = %s
            """, (contract_id, database_id))
