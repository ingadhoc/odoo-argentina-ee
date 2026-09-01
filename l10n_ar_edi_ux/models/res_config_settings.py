from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    arba_cit = fields.Char(related="company_id.arba_cit", readonly=False)
    # TODO 20.0: drop along with the rest of the odoo/enterprise#102032 backport.
    l10n_ar_invoice_pdf_legend_ux = fields.Selection(related="company_id.l10n_ar_invoice_pdf_legend_ux", readonly=False)
