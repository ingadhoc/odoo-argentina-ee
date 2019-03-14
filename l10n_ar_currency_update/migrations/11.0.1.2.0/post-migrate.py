##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """ Set currency_next_execution_date = manually for all the companies
    without next execution date. This way we avoid ambiguity and we let the
    user activate the feature by hand
    """
    env['res.company'].search(
        [('currency_next_execution_date', '=', False)]).write({
            'currency_interval_unit': 'manually'})
