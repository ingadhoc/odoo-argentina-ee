from openupgradelib import openupgrade


def migrate(cr, version):
    """Delete orphaned account.report.expression records for IVA withholding/perception lines.

    These expressions were auto-created (without XML IDs) when the lines used the old
    domain_formula field. Now that the XML uses explicit expression_ids with proper XML IDs,
    Odoo can't find them by XML ID and tries to INSERT new ones, hitting the unique constraint
    on (report_line_id, label). We delete the orphaned records so the data load can recreate
    them with the correct XML ID registration.
    """
    openupgrade.logged_query(
        cr,
        """
        DELETE FROM account_report_expression
        WHERE report_line_id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'l10n_ar_account_reports'
            AND model = 'account.report.line'
            AND name IN (
                'l10n_ar_iva_report_iva_withholdings_line',
                'l10n_ar_iva_report_iva_perceptions_line'
            )
        )
        AND label = 'balance'
        AND id NOT IN (
            SELECT res_id FROM ir_model_data
            WHERE model = 'account.report.expression'
            AND name IN (
                'l10n_ar_iva_report_iva_withholdings_line_balance',
                'l10n_ar_iva_report_iva_perceptions_line_balance'
            )
        )
        """,
    )
