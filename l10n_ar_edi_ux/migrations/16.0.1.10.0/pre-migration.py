from openupgradelib import openupgrade
import logging
logger = logging.getLogger(__name__)

@openupgrade.migrate()
def migrate(env, version):
    logger.info('Forzamos la actualización de la vista de account_journal_views en módulo account.payment para que pueda aplicarse correctamente este cambio https://github.com/odoo/odoo/pull/164208/')
    openupgrade.load_data(env.cr, 'account_payment', 'views/account_journal_views.xml')
