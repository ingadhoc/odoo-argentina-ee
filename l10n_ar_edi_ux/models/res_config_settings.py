from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    arba_cit = fields.Char(related="company_id.arba_cit", readonly=False)
    l10n_ar_invoice_pdf_legend = fields.Selection(related="company_id.l10n_ar_invoice_pdf_legend", readonly=False)
