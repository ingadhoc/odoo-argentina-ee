##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _is_edi_ux_demo_company(self, company):
        return company == self.env.ref("l10n_ar_edi_ux.edi_ux_parent_company", raise_if_not_found=False)

    @api.model
    def _get_demo_data(self, company=False):
        if self._is_edi_ux_demo_company(company):
            return {}
        return super()._get_demo_data(company)

    def _post_load_demo_data(self, company=False):
        if self._is_edi_ux_demo_company(company):
            return
        return super()._post_load_demo_data(company)
