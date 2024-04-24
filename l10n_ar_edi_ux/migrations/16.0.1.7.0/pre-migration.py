from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    env.cr.execute("DELETE FROM ir_ui_view WHERE arch_db::text LIKE '%check_debit_journal_id%'")
