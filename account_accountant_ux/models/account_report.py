from odoo import models
from odoo.tools.misc import get_user_companies


class AccountReport(models.AbstractModel):

    _inherit = 'account.report'

    def _build_options(self, previous_options=None):
        """ Remove inactive companies from financial report filters.
        """
        previous_options = previous_options or {}
        if previous_options.get('multi_company'):
            # Previous options are stored in web browser's internal storage.
            company_ids = [item['id']
                           for item in previous_options["multi_company"]]
            companies = self.env["res.company"].browse(
                company_ids).filtered('active')
            previous_options['multi_company'] = [
                item
                for item in previous_options['multi_company']
                if item['id'] in companies.ids]
        else:
            # First time execution, we inject the property adding a filtered()
            company_ids = get_user_companies(self._cr, self.env.user.id)
            if len(company_ids) > 1:
                companies = self.env['res.company'].browse(
                    company_ids).filtered('active')
                previous_options['multi_company'] = [
                    {'id': c.id, 'name': c.name, 'selected': True
                     if c.id == self.env.user.company_id.id else False}
                    for c in companies]
        return super()._build_options(previous_options)
