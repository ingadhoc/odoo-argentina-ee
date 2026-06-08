##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64
import logging

from odoo import api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Tabla de equivalencias letra → alícuota del padrón SIRCIP
SIRCIP_LETTER_ALIQUOT = {
    "A": 0.00, "B": 0.01, "C": 0.05, "D": 0.10,
    "E": 0.20, "F": 0.30, "G": 0.40, "H": 0.50,
    "I": 0.60, "J": 0.70, "K": 0.80, "L": 1.00,
    "M": 1.20, "N": 1.40, "O": 1.50, "P": 1.60,
    "Q": 1.80, "R": 2.00, "S": 2.50, "T": 3.00,
    "U": 3.50, "V": 4.00, "W": 4.50, "X": 5.00,
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

    def _get_sircip_aliquot(self, partner):
        """Parsea el archivo TXT del padrón SIRCIP para un CUIT dado.

        Formato del archivo TXT SIRCIP (por definir según especificación oficial):
        TODO: completar la especificación exacta de campos y posiciones una vez
        revisado el documento oficial en doc/sircip/.

        Campos esperados por línea (separados por ';'):
          [0] CUIT del contribuyente (sin guiones)
          [1] Letra de alícuota (A-X)
          [2] CRC / código de verificación
          [3] Campo 7 (26 caracteres: 25 provincias + carácter de control)

        :param partner: res.partner con el CUIT a buscar
        :return: tuple (is_in_padron, aliquot_per, campo7_string)
                 - is_in_padron: bool
                 - aliquot_per: float (0.0 si no está en el padrón)
                 - campo7_string: str de 26 chars o '' si no está en el padrón
        """
        self.ensure_one()
        cuit = partner.vat or ""
        cuit_clean = cuit.replace("-", "").strip()

        file_content = base64.b64decode(self.file_padron)
        # TODO: verificar si el archivo puede venir comprimido (ZIP/RAR)
        try:
            lines = file_content.decode("latin-1").splitlines()
        except Exception:
            lines = file_content.decode("utf-8", errors="replace").splitlines()

        for line in lines:
            if not line.strip():
                continue
            values = [v.strip() for v in line.split(";")]
            if len(values) < 4:
                continue
            # TODO: validar posición exacta del CUIT según la especificación oficial
            line_cuit = values[0].replace("-", "").strip()
            if line_cuit != cuit_clean:
                continue

            letra = values[1].upper() if len(values) > 1 else ""
            crc = values[2] if len(values) > 2 else ""
            campo7 = values[3] if len(values) > 3 else ""

            aliquot = SIRCIP_LETTER_ALIQUOT.get(letra, 0.0)
            _logger.info(
                "SIRCIP padrón: CUIT %s → letra %s (%.2f%%), campo7=%s",
                cuit_clean, letra, aliquot, campo7[:10] + "..." if len(campo7) > 10 else campo7,
            )
            return True, aliquot, campo7, crc

        return False, 0.0, "", ""
