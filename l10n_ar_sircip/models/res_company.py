##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64
import re

from dateutil.relativedelta import relativedelta
from odoo import fields, models
from odoo.tools import file_open


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ar_sircip_agent = fields.Boolean(
        string="SIRCIP Perception Agent",
        help="The company is a SIRCIP perception agent. Saving the settings with this option creates the SIRCIP "
        "taxes, account, fiscal position and settlement journal, and adds the SIRCIP line to the fiscal positions "
        "with perceptions.",
    )
    l10n_ar_sircip_account_id = fields.Many2one(
        "account.account",
        string="SIRCIP Perception Account",
        check_company=True,
        help="Account of the SIRCIP perceptions. If empty, it is created next to the applied IIBB perceptions of the "
        "chart of accounts.",
    )

    def _l10n_ar_sircip_setup(self):
        """Create or complete the SIRCIP data of agent companies. Safe to run repeatedly."""
        from ..hooks import _create_sircip_data_for_company

        sircip_state = self.env.ref("l10n_ar_sircip.state_ar_sircip")
        for company in self.filtered(lambda c: c.l10n_ar_sircip_agent and c.account_fiscal_country_id.code == "AR"):
            _create_sircip_data_for_company(self.env, company, sircip_state)

    def _l10n_ar_sircip_load_test_padron(self, date):
        """Load the demo padron as the padron of the month of ``date``, with fictitious CUITs, so the company can
        try SIRCIP without a real file. Does nothing if that month already has a SIRCIP padron."""
        self.ensure_one()
        Padron = self.env["res.company.jurisdiction.padron"]
        sircip_state = self.env.ref("l10n_ar_sircip.state_ar_sircip")
        month_start = date + relativedelta(day=1)
        existing = Padron.search(
            [
                ("company_id", "=", self.id),
                ("state_id", "=", sircip_state.id),
                ("l10n_ar_padron_from_date", "=", month_start),
            ],
            limit=1,
        )
        if existing:
            return existing
        period = month_start.strftime("%Y%m").encode()
        with file_open("l10n_ar_sircip/demo/padron_sircip_demo.txt", "rb") as demo_file:
            content = re.sub(rb"^\d{6},", period + b",", demo_file.read(), flags=re.M)
        return Padron.create(
            {
                "company_id": self.id,
                "state_id": sircip_state.id,
                "l10n_ar_padron_from_date": month_start,
                "l10n_ar_padron_to_date": month_start + relativedelta(months=1, days=-1),
                "filename": "padron_sircip_PRUEBA_%s.txt" % period.decode(),
                "file_padron": base64.b64encode(content),
            }
        )
