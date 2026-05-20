<<<<<<< f235ca7b9eb52beeae67565baf965c0a1b72e7d1
import base64

from cryptography import x509
from odoo import api, fields, models


class CertificateCertificate(models.Model):
    _inherit = "certificate.certificate"

    content_filename = fields.Char()

    l10n_ar_subject_serial_number = fields.Char(
        compute="_compute_l10n_ar_subject_serial_number",
        string="Belongs to",
        help="This is the CUIT information of the related ARCA Certificate.",
    )

    @api.depends("pem_certificate")
    def _compute_l10n_ar_subject_serial_number(self):
        """Compute the subject serial number needed to then check if the afip connection can be
        re use for multiple branches if they share the same certificate CUIT."""
        for certificate in self:
            pem_certificate = certificate.with_context(bin_size=False).pem_certificate
            if not certificate.l10n_ar_subject_serial_number and pem_certificate:
                cert = x509.load_pem_x509_certificate(base64.b64decode(pem_certificate))
                l10n_ar_subject_serial_number = cert.subject.get_attributes_for_oid(x509.oid.NameOID.SERIAL_NUMBER)
                if l10n_ar_subject_serial_number:
                    certificate.l10n_ar_subject_serial_number = l10n_ar_subject_serial_number[0].value
||||||| 289e24e5865df0d99ce87dc017f7a2350f730d90
=======
import base64

from cryptography import x509
from odoo import api, fields, models


class CertificateCertificate(models.Model):
    _inherit = "certificate.certificate"

    l10n_ar_subject_serial_number = fields.Char(
        compute="_compute_l10n_ar_subject_serial_number",
        string="Belongs to",
        help="This is the CUIT information of the related ARCA Certificate.",
    )

    @api.depends("pem_certificate")
    def _compute_l10n_ar_subject_serial_number(self):
        """Compute the subject serial number needed to then check if the afip connection can be
        re use for multiple branches if they share the same certificate CUIT."""
        for certificate in self:
            pem_certificate = certificate.with_context(bin_size=False).pem_certificate
            if not certificate.l10n_ar_subject_serial_number and pem_certificate:
                cert = x509.load_pem_x509_certificate(base64.b64decode(pem_certificate))
                l10n_ar_subject_serial_number = cert.subject.get_attributes_for_oid(x509.oid.NameOID.SERIAL_NUMBER)
                if l10n_ar_subject_serial_number:
                    certificate.l10n_ar_subject_serial_number = l10n_ar_subject_serial_number[0].value
>>>>>>> 8dd73ee8fbe9eb9c070b310996fc480c386739c4
