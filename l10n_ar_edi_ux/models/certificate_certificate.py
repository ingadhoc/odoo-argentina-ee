from odoo import fields, models


class CertificateCertificate(models.Model):
    _inherit = "certificate.certificate"

    content_filename = fields.Char()
