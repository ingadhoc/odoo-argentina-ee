from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(
        env.cr, 'account_journal_book_report',
        'migrations/13.0.1.1.0/noupdate_changes.xml')
