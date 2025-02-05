import logging

_logger = logging.getLogger(__name__)


def l10n_ar_account_tax_settlement_post_init_hook(env):
    """Al instalar este módulo (l10n_ar_account_tax_settlement), en caso de que existan compañías argentinas y con plan de cuentas ya establecido entonces a esas compañías les creamos los diarios de liquidación correspondientes."""

    # Verificamos que la compañía sea argentina. Agregamos ('parent_id', '=', False) en el dominio de la búsqueda porque las branches de una compañía
    # usan los mismos impuestos que la compañía padre. Algo similar a esto se aplicó en este pr https://github.com/ingadhoc/odoo-argentina-ee/pull/446
    ar_companies = env["res.company"].search([("chart_template", "in", ("ar_base", "ar_ri", "ar_ex"))])
    for company in ar_companies:
        ChartTemplate = env["account.chart.template"].with_company(company)
        if journals_to_create := env["account.chart.template"]._get_latam_withholding_account_journal(
            template_code=company.chart_template, company=company
        ):
            ChartTemplate._load_data({"account.journal": journals_to_create})

    # Dejamos registro en los logs de las compañías en las cuales se estableció el código de impuesto
    if ar_companies:
        _logger.info(
            "Se crearon los diarios de liquidación para las compañías %s." % ", ".join(ar_companies.mapped("name"))
        )
