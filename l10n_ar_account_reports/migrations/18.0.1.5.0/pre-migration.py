from openupgradelib import openupgrade


def migrate(cr, version):
    """Migrate accounts from old 'ar_esp_patrimonio_neto' tag to new specific tags.

    The old tag 'ar_esp_patrimonio_neto' is being removed and split into three
    more specific tags: 'ar_esp_capital', 'ar_esp_reservas', and 'ar_esp_resultados'.

    This migration removes the old tag assignment from all accounts that have it.
    The new tags will be assigned automatically by the post-migration hook based
    on the account type.
    """
    # Remove all account assignments for the old patrimonio_neto tag
    openupgrade.logged_query(
        cr,
        """
        DELETE FROM account_account_account_tag
        WHERE account_account_tag_id IN (
            SELECT res_id
            FROM ir_model_data
            WHERE module = 'l10n_ar_account_reports'
            AND model = 'account.account.tag'
            AND name = 'ar_esp_patrimonio_neto'
        )
        """,
    )

    # Delete old equity line structure to avoid conflicts with new structure
    # The new structure uses children_ids instead of direct domain expressions
    openupgrade.logged_query(
        cr,
        """
        DELETE FROM account_report_line
        WHERE id IN (
            SELECT res_id
            FROM ir_model_data
            WHERE module = 'l10n_ar_account_reports'
            AND name IN (
                'account_financial_report_l10n_ar_estado_patrimonial_line_equity',
                'account_financial_report_l10n_ar_estado_patrimonial_line_total_liabilities_equity'
            )
        )
        """,
    )
