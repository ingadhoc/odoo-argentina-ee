from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    env.cr.execute(
        "UPDATE account_journal SET settlement_tax = 'iibb_aplicado_arba_desde_01032026' WHERE settlement_tax = 'iibb_aplicado'"
    )
    env.cr.execute(
        "UPDATE account_journal SET settlement_tax = 'iibb_aplicado_arba_act_7_desde_01032026' WHERE settlement_tax = 'iibb_aplicado_act_7'"
    )
