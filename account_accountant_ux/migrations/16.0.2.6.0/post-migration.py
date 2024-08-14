from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Sets filter by same amount in bank reconciliation in True by default"""
    env['ir.config_parameter'].set_param('account_accountant_ux.use_search_filter_amount', 'True')
