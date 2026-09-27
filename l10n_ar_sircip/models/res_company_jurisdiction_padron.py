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

# Tabla de equivalencias letra → alícuota del padrón SIRCIP.
# Fuente: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf
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
        """Extendemos para permitir cargar el padrón con la provincia ficticia SIRCIP."""
        sircip_state = self._get_sircip_state()
        non_sircip = self.filtered(lambda r: r.state_id != sircip_state)
        return super(ResCompanyJurisdictionPadron, non_sircip).check_state_id()

    @api.constrains("state_id", "file_padron", "l10n_ar_padron_from_date")
    def _check_sircip_period(self):
        """El período del archivo (primera columna) tiene que ser el mes del padrón: la Comisión Arbitral publica el
        del mes siguiente el día 22, y cargarlo en el mes equivocado cambia las percepciones de todo el mes."""
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
        """Contenido del padrón SIRCIP. Acepta el TXT o un ZIP con un solo archivo adentro."""
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
        """Período (AAAAMM) de la primera línea de datos del padrón, salteando el encabezado."""
        for line in io.StringIO(self._get_sircip_text()):
            value = line.split(",", 1)[0].strip()
            if value.isdigit():
                return value
        return ""

    def _get_sircip_aliquot(self, partner):
        """Parsea el archivo TXT del padrón SIRCIP para un CUIT dado.

        Formato del archivo (CSV separado por comas, primera línea = encabezado):
        periodo, cuit, razon_social_contri, jurisdiccion_sede, crc, alicuota_unica_letra, campo7

        Ejemplo de línea:
        202602,30100100106,MI EMPRESA SA,904,34,B,5225355222512555552512420

        Campo 7 — lectura (25 chars, derecha a izquierda):
        - índice 24 (rightmost) siempre '0' (descartar)
        - índice de jurisdicción JC: 924 - JC  (ej: CABA=901 → índice 23)
        - valores 1-5: tipo de percepción a aplicar en esa provincia

        :param partner: res.partner con el CUIT a buscar
        :return: tuple (is_in_padron, aliquot_per, campo7_string, crc_str, letra)
        """
        self.ensure_one()
        cuit_clean = (partner.vat or "").replace("-", "").strip()
        not_found = (False, 0.0, "", "", "")
        if not cuit_clean:
            return not_found

        text = self._get_sircip_text()

        # El padrón trae a todos los contribuyentes de Convenio Multilateral: en vez de partir el archivo
        # en líneas, buscamos el CUIT (columna 2) y leemos solo esa línea.
        pos = text.find(",%s," % cuit_clean)
        while pos != -1:
            start = text.rfind("\n", 0, pos) + 1
            end = text.find("\n", pos)
            values = [v.strip() for v in text[start : end if end != -1 else None].split(",")]
            # Columnas: [0]=periodo, [1]=cuit, [2]=razon_social, [3]=jurisdiccion, [4]=crc, [5]=letra, [6]=campo7
            if len(values) >= 7 and values[1].replace("-", "") == cuit_clean:
                letra = values[5].upper()
                aliquot = SIRCIP_LETTER_ALIQUOT.get(letra, 0.0)
                _logger.debug("SIRCIP padrón: CUIT ...%s → letra %s (%.2f%%)", cuit_clean[-4:], letra, aliquot)
                return True, aliquot, values[6], values[4], letra
            pos = text.find(",%s," % cuit_clean, pos + 1)
        return not_found
