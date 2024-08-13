from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(
        env, 'account_tax_settlement', 'data/account_report_data.xml')
