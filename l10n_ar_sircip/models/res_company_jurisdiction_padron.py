##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64
import io
import logging
import zipfile

from odoo import api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Padron letter -> aliquot (%)
# Source: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf
SIRCIP_LETTER_ALIQUOT = {
    "A": 0.00,
    "B": 0.01,
    "C": 0.05,
    "D": 0.10,
    "E": 0.20,
    "F": 0.30,
    "G": 0.40,
    "H": 0.50,
    "I": 0.60,
    "J": 0.70,
    "K": 0.80,
    "L": 1.00,
    "M": 1.20,
    "N": 1.40,
    "O": 1.50,
    "P": 1.60,
    "Q": 1.80,
    "R": 2.00,
    "S": 2.50,
    "T": 3.00,
    "U": 3.50,
    "V": 4.00,
    "W": 4.50,
    "X": 5.00,
}


class ResCompanyJurisdictionPadron(models.Model):
    _inherit = "res.company.jurisdiction.padron"

    def _get_sircip_state(self):
        return self.env.ref("l10n_ar_sircip.state_ar_sircip", raise_if_not_found=False)

    @api.constrains("state_id")
    def check_state_id(self):
        """Allow loading the padron for the SIRCIP pseudo-province."""
        sircip_state = self._get_sircip_state()
        non_sircip = self.filtered(lambda r: r.state_id != sircip_state)
        return super(ResCompanyJurisdictionPadron, non_sircip).check_state_id()

    @api.constrains("state_id", "file_padron", "l10n_ar_padron_from_date")
    def _check_sircip_period(self):
        """The file period (first column) must match the padron month: next month's file is out on the 22nd."""
        sircip_state = self._get_sircip_state()
        for rec in self.filtered(lambda r: r.state_id == sircip_state and r.file_padron and r.l10n_ar_padron_from_date):
            period = rec._get_sircip_period()
            expected = rec.l10n_ar_padron_from_date.strftime("%Y%m")
            if period != expected:
                raise ValidationError(
                    self.env._(
                        "The SIRCIP padron file is for period %(period)s, but it is loaded from %(date)s. Load it "
                        "for the month of its period.",
                        period=period or "?",
                        date=rec.l10n_ar_padron_from_date,
                    )
                )

    def _get_sircip_text(self):
        """Padron content, from the TXT or from a ZIP holding a single file."""
        self.ensure_one()
        content = base64.b64decode(self.file_padron or b"")
        if zipfile.is_zipfile(io.BytesIO(content)):
            with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
                names = [name for name in zip_file.namelist() if not name.endswith("/")]
                if len(names) != 1:
                    raise ValidationError(self.env._("The SIRCIP padron ZIP file must contain a single file."))
                content = zip_file.read(names[0])
        return content.decode("latin-1")

    def _get_sircip_period(self):
        """Period (YYYYMM) of the first data line, skipping the header."""
        for line in io.StringIO(self._get_sircip_text()):
            value = line.split(",", 1)[0].strip()
            if value.isdigit():
                return value
        return ""

    def _get_sircip_aliquot(self, partner):
        """Look up the partner's CUIT in the SIRCIP padron.

        Line format (CSV with header):
        periodo,cuit,razon_social_contri,jurisdiccion_sede,crc,alicuota_unica_letra,campo7

        :return: tuple (is_in_padron, aliquot, campo7, crc, letra)
        """
        self.ensure_one()
        cuit_clean = (partner.vat or "").replace("-", "").strip()
        not_found = (False, 0.0, "", "", "")
        if not cuit_clean:
            return not_found

        text = self._get_sircip_text()

        # Performance: the padron lists every Convenio Multilateral taxpayer, so find the CUIT, not every line
        pos = text.find(",%s," % cuit_clean)
        while pos != -1:
            start = text.rfind("\n", 0, pos) + 1
            end = text.find("\n", pos)
            values = [v.strip() for v in text[start : end if end != -1 else None].split(",")]
            if len(values) >= 7 and values[1].replace("-", "") == cuit_clean:
                letra = values[5].upper()
                aliquot = SIRCIP_LETTER_ALIQUOT.get(letra, 0.0)
                _logger.debug("SIRCIP padrón: CUIT ...%s → letra %s (%.2f%%)", cuit_clean[-4:], letra, aliquot)
                return True, aliquot, values[6], values[4], letra
            pos = text.find(",%s," % cuit_clean, pos + 1)
        return not_found
