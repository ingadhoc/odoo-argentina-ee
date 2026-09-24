##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ar_sircip_agent = fields.Boolean(
        string="SIRCIP Perception Agent",
        help="The company is a SIRCIP perception agent. Saving the settings with this option creates the SIRCIP "
        "taxes, account, fiscal position and settlement journal, and adds the SIRCIP line to the fiscal positions "
        "with perceptions.",
    )

    def _l10n_ar_sircip_setup(self):
        """Crea o completa los datos SIRCIP de las compañías agentes. Se puede correr las veces que haga falta."""
        from ..hooks import _create_sircip_data_for_company

        sircip_state = self.env.ref("l10n_ar_sircip.state_ar_sircip")
        for company in self.filtered(lambda c: c.l10n_ar_sircip_agent and c.account_fiscal_country_id.code == "AR"):
            _create_sircip_data_for_company(self.env, company, sircip_state)
