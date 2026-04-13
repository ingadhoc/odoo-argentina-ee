import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove obsolete account.report.line records.

    The l10n_ar_pba_report_pba_withholdings_line_a122r record was an old
    implementation that needs to be cleaned up. Simply removing it from the
    XML file is not enough for existing databases - this migration ensures
    the record is deleted from the database to avoid orphaned references.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    # IDs of obsolete records to delete
    obsolete_line_ids = [
        "l10n_ar_account_reports.l10n_ar_pba_report_pba_withholdings_line_a122r",
    ]

    for xml_id in obsolete_line_ids:
        try:
            record = env.ref(xml_id, raise_if_not_found=False)
            if record:
                record.unlink()
                _logger.info("✓ Deleted obsolete record: %s", xml_id)
            else:
                _logger.info("⊘ Record not found (already deleted?): %s", xml_id)
        except Exception as e:
            _logger.warning("⚠ Error deleting %s: %s", xml_id, e)
