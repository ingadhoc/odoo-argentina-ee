import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Replace balance column with amount_residual column in followup report."""
    _logger.info("Running post init hook to setup amount_residual column in followup report")

    # Get the followup report
    followup_report = env.ref("account_reports.followup_report", raise_if_not_found=False)

    if not followup_report:
        _logger.warning("Followup report not found, skipping initialization")
        return

    # Remove balance column if exists
    balance_column = followup_report.column_ids.filtered(lambda c: c.expression_label == "balance")
    if balance_column:
        balance_column.unlink()
        _logger.info("Removed balance column from followup report")

    # Check if amount_residual column already exists
    existing_column = followup_report.column_ids.filtered(lambda c: c.expression_label == "amount_residual")

    if not existing_column:
        # Create amount_residual column
        env["account.report.column"].create(
            {
                "name": "Importe Residual",
                "expression_label": "amount_residual",
                "report_id": followup_report.id,
                "sequence": 100,
                "figure_type": "monetary",
            }
        )
        _logger.info("Created amount_residual column in followup report")
    else:
        _logger.info("Amount residual column already exists in followup report")
