##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.addons.l10n_ar_reports.report.account_ar_vat_line import AccountArVatLine

from odoo import api

from . import models
from . import wizards


def monkey_patches():
# monkey patch
    @api.model
    def _ar_vat_line_build_query(self, tables='account_move_line', where_clause='', where_params=None,
                                    column_group_key='', tax_types=('sale', 'purchase')):
        """Returns the SQL Select query fetching account_move_lines info in order to build the pivot view for the VAT summary.
        This method is also meant to be used outside this model, which is the reason why it gives the opportunity to
        provide a few parameters, for which the defaults are used in this model.

        The query is used to build the VAT book report"""
        if where_params is None:
            where_params = []

        query = f"""
                WITH tax_lines AS (
                    SELECT
                        aml.id AS move_line_id,
                        aml.move_id,
                        ntg.l10n_ar_vat_afip_code AS vat_code,
                        ntg.l10n_ar_tribute_afip_code AS tribute_code,
                        nt.type_tax_use AS type_tax_use,
                        aml.balance
                    FROM account_move_line aml
                    LEFT JOIN account_tax nt ON aml.tax_line_id = nt.id
                    LEFT JOIN account_tax_group ntg ON nt.tax_group_id = ntg.id
                    WHERE aml.tax_line_id IS NOT NULL
                ),
                base_lines AS (
                    SELECT
                        aml.id AS move_line_id,
                        aml.move_id,
                        MAX(btg.l10n_ar_vat_afip_code) AS vat_code, -- MAX is used to avoid duplicates when multiple taxes exist on a line
                        MAX(bt.type_tax_use) AS type_tax_use,
                        aml.balance
                    FROM account_move_line aml
                    JOIN account_move_line_account_tax_rel amltr ON aml.id = amltr.account_move_line_id
                    JOIN account_tax bt ON amltr.account_tax_id = bt.id
                    JOIN account_tax_group btg ON bt.tax_group_id = btg.id
                    GROUP BY aml.id, aml.move_id, aml.balance
                )
                SELECT
                    %s AS column_group_key,
                    account_move.id,
                    (CASE WHEN lit.l10n_ar_afip_code = '80' THEN rp.vat ELSE NULL END) AS cuit,
                    art.name AS afip_responsibility_type_name,
                    rp.name AS partner_name,
                    COALESCE(tax.type_tax_use, base.type_tax_use) AS tax_type,
                    account_move.id AS move_id,
                    account_move.move_type,
                    account_move.date,
                    account_move.invoice_date,
                    account_move.partner_id,
                    account_move.journal_id,
                    account_move.name AS move_name,
                    account_move.l10n_ar_afip_responsibility_type_id AS afip_responsibility_type_id,
                    account_move.l10n_latam_document_type_id AS document_type_id,
                    account_move.state,
                    account_move.company_id,
                    SUM(CASE WHEN base.vat_code IN ('4', '5', '6', '8', '9') THEN base.balance ELSE 0 END) AS taxed,
                    SUM(CASE WHEN base.vat_code = '4' THEN base.balance ELSE 0 END) AS base_10,
                    SUM(CASE WHEN tax.vat_code = '4' THEN tax.balance ELSE 0 END) AS vat_10,
                    SUM(CASE WHEN base.vat_code = '5' THEN base.balance ELSE 0 END) AS base_21,
                    SUM(CASE WHEN tax.vat_code = '5' THEN tax.balance ELSE 0 END) AS vat_21,
                    SUM(CASE WHEN base.vat_code = '6' THEN base.balance ELSE 0 END) AS base_27,
                    SUM(CASE WHEN tax.vat_code = '6' THEN tax.balance ELSE 0 END) AS vat_27,
                    SUM(CASE WHEN base.vat_code = '8' THEN base.balance ELSE 0 END) AS base_5,
                    SUM(CASE WHEN tax.vat_code = '8' THEN tax.balance ELSE 0 END) AS vat_5,
                    SUM(CASE WHEN base.vat_code = '9' THEN base.balance ELSE 0 END) AS base_25,
                    SUM(CASE WHEN tax.vat_code = '9' THEN tax.balance ELSE 0 END) AS vat_25,
                    SUM(CASE WHEN base.vat_code IN ('0', '1', '2', '3', '7') THEN base.balance ELSE 0 END) AS not_taxed,
                    SUM(CASE WHEN tax.tribute_code = '06' THEN tax.balance ELSE 0 END) AS vat_per,
                    SUM(CASE WHEN tax.vat_code IS NULL AND tax.tribute_code != '06' THEN tax.balance ELSE 0 END) AS other_taxes,
                    SUM(account_move_line.balance) AS total
                FROM
                    {tables}
                JOIN
                    account_move ON account_move_line.move_id = account_move.id
                LEFT JOIN
                    tax_lines tax ON tax.move_line_id = account_move_line.id
                LEFT JOIN
                    base_lines base ON base.move_line_id = account_move_line.id
                LEFT JOIN
                    res_partner rp ON rp.id = account_move.commercial_partner_id
                LEFT JOIN
                    l10n_latam_identification_type lit ON rp.l10n_latam_identification_type_id = lit.id
                LEFT JOIN
                    l10n_ar_afip_responsibility_type art ON account_move.l10n_ar_afip_responsibility_type_id = art.id
                WHERE
                    (account_move_line.tax_line_id IS NOT NULL OR base.vat_code IS NOT NULL)
                        AND (tax.type_tax_use IN %s OR base.type_tax_use IN %s)
                {where_clause}
                GROUP BY
                    account_move.id, art.name, rp.id, rp.name, rp.vat, lit.id,
                    account_move.move_type,
                    account_move.date,
                    account_move.invoice_date,
                    account_move.partner_id,
                    account_move.journal_id,
                    account_move.name,
                    account_move.l10n_ar_afip_responsibility_type_id,
                    account_move.l10n_latam_document_type_id,
                    account_move.state,
                    account_move.company_id,
                    COALESCE(tax.type_tax_use, base.type_tax_use)

                ORDER BY
                    account_move.invoice_date, account_move.name"""
        return query, [column_group_key, tax_types, tax_types, *where_params]

    AccountArVatLine._ar_vat_line_build_query = _ar_vat_line_build_query
