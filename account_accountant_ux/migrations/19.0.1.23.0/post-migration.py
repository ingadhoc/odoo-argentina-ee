import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Same values as data/account_report_settlement.xml, which is noupdate and only loads on install.
SETTLEMENT_VALUES = {
    "account_reports.profit_and_loss": {
        "allow_settlement": True,
        "settlement_title": "Asiento de refundición",
        "settlement_allow_unbalanced": True,
    },
    "account_reports.balance_sheet": {
        "allow_settlement": True,
        "settlement_title": "Generar asiento de cierre",
    },
}


def migrate(cr, version):
    """Enable the settlement buttons on the generic P&L and Balance Sheet.

    Reports that already have the option on (e.g. set up in 18) are left as they are.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, values in SETTLEMENT_VALUES.items():
        report = env.ref(xmlid, raise_if_not_found=False)
        if not report or report.allow_settlement:
            continue
        report.write(values)
        _logger.info("Settlement button enabled on report %s", xmlid)
