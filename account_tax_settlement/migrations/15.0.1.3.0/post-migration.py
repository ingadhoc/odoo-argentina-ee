from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.logged_query(env.cr, """
        UPDATE account_journal
        SET settlement_account_id = default_account_id
        WHERE default_account_id is not null
        AND tax_settlement is not null
        AND type = 'general'
    """)
