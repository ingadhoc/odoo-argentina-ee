##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
{
    "name": "SIRCIP - Percepciones Convenio Multilateral",
    "version": "18.0.1.0.0",
    "category": "Localization/Argentina",
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "LGPL-3",
    "summary": "Módulo exclusivo para empresas Agentes de Percepción del SIRCIP (Sistema de Recaudación del Control sobre Ingresos Brutos de Convenio Multilateral). Gestiona la carga de padrones, el cálculo de alícuotas y sobrealícuotas por provincia, y la generación del TXT de presentación de DDJJ.",
    "depends": [
        "l10n_ar_account_tax_settlement",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/res_country_state_data.xml",
        "views/res_country_state_views.xml",
    ],
    "post_init_hook": "l10n_ar_sircip_post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
}
