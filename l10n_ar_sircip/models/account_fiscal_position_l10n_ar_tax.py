##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Posición de cada jurisdicción en el campo 7 del padrón SIRCIP.
# El campo 7 tiene 26 posiciones: 25 provincias ordenadas numéricamente + 1 char de control.
# Fuente de jurisdiction_code: l10n_ar_ux/models/res_country_state.py (_compute_jurisdiction_code)
# Mapa: jurisdiction_code → índice (0-based) en el string de 26 chars
# TODO: verificar el orden exacto del campo 7 con la especificación oficial del SIRCIP.
SIRCIP_CAMPO7_POSITION = {
    "901": 0,   # CABA (code C)
    "902": 1,   # Buenos Aires (code B)
    "903": 2,   # Catamarca (code K)
    "904": 3,   # Córdoba (code X)
    "905": 4,   # Corrientes (code W)
    "906": 5,   # Chaco (code H)
    "907": 6,   # Chubut (code U)
    "908": 7,   # Entre Ríos (code E)
    "909": 8,   # Formosa (code P)
    "910": 9,   # Jujuy (code Y)
    "911": 10,  # La Pampa (code L)
    "912": 11,  # La Rioja (code F)
    "913": 12,  # Mendoza (code M)
    "914": 13,  # Misiones (code N)
    "915": 14,  # Neuquén (code Q)
    "916": 15,  # Río Negro (code R)
    "917": 16,  # Salta (code A)
    "918": 17,  # San Juan (code J)
    "919": 18,  # San Luis (code D)
    "920": 19,  # Santa Cruz (code Z)
    "921": 20,  # Santa Fe (code S)
    "922": 21,  # Santiago del Estero (code G)
    "923": 22,  # Tierra del Fuego (code V)
    "924": 23,  # Tucumán (code T)
    # posición 24: posiblemente reservada o futura provincia
    # posición 25: carácter de control
}


class AccountFiscalPositionL10nArTax(models.Model):
    _inherit = "account.fiscal.position.l10n_ar_tax"

    def _get_sircip_state(self):
        return self.env.ref("l10n_ar_sircip.state_ar_sircip", raise_if_not_found=False)

    @api.constrains("webservice", "default_tax_id")
    def _check_webservice_available(self):
        """Extendemos para permitir webservice='padron' con la provincia ficticia SIRCIP."""
        sircip_state = self._get_sircip_state()
        if sircip_state:
            non_sircip_padron = self.filtered(
                lambda r: not (
                    r.webservice == "padron"
                    and r.default_tax_id.l10n_ar_state_id == sircip_state
                )
            )
        else:
            non_sircip_padron = self
        return super(AccountFiscalPositionL10nArTax, non_sircip_padron)._check_webservice_available()

    def _get_padron_data(self, partner, date, to_date):
        """Override para manejar el padrón SIRCIP cuando el impuesto apunta a la
        provincia ficticia SIRCIP."""
        sircip_state = self._get_sircip_state()
        if sircip_state and self.default_tax_id.l10n_ar_state_id == sircip_state:
            return self._get_sircip_padron_data(partner, date, to_date)
        return super()._get_padron_data(partner, date, to_date)

    def _get_sircip_padron_data(self, partner, date, to_date):
        """Obtiene alícuota SIRCIP del padrón cargado para el período dado.

        :return: (aliquot_or_None, ref_string)
                 aliquot_or_None: float o None (None = no inscripto → usa default_tax_id)
                 ref_string: string con datos para trazabilidad almacenado en l10n_ar.partner.tax
        """
        self.ensure_one()
        sircip_state = self._get_sircip_state()
        padron_file = self._search_padron_file(sircip_state, date)
        if not padron_file:
            raise UserError(
                _(
                    "No hay padrón SIRCIP subido para el período %s a %s. "
                    "Debe subirlo en 'Contabilidad / Configuración / AFIP / Padrón de Alícuotas por compañía' "
                    "usando la provincia 'SIRCIP'."
                )
                % (date, to_date)
            )

        is_in_padron, aliquot, campo7, crc = padron_file._get_sircip_aliquot(partner)

        if not is_in_padron:
            ref = _("SIRCIP No Inscripto (no figura en padrón)")
            return None, ref

        ref = "SIRCIP | crc:%s | campo7:%s" % (crc, campo7)
        return aliquot, ref

    def _get_sircip_campo7_digit(self, campo7, delivery_state):
        """Obtiene el dígito del campo 7 para la provincia de entrega dada.

        :param campo7: string de 26 posiciones del padrón SIRCIP
        :param delivery_state: res.country.state del domicilio de entrega
        :return: int (dígito 0-5) o 0 si la provincia no participa
        """
        if not campo7 or not delivery_state:
            return 0
        jcode = delivery_state.jurisdiction_code or ""
        pos = SIRCIP_CAMPO7_POSITION.get(jcode)
        if pos is None or pos >= len(campo7):
            return 0
        char = campo7[pos]
        try:
            return int(char)
        except ValueError:
            return 0

    def _get_tax_from_ws(self, partner, date):
        """Override para SIRCIP: cuando el dígito del campo 7 requiere múltiples
        impuestos (dígitos 2, 4, 5), los retorna como un recordset."""
        sircip_state = self._get_sircip_state()
        if not (sircip_state and self.default_tax_id.l10n_ar_state_id == sircip_state):
            return super()._get_tax_from_ws(partner, date)

        from_date = date + relativedelta(day=1)
        to_date = from_date + relativedelta(days=-1, months=+1)

        aliquot, ref = self._get_sircip_padron_data(partner, from_date, to_date)

        # Determinar impuesto base
        if aliquot is None:
            base_tax = self.default_tax_id
        else:
            base_tax = self._ensure_tax(aliquot)

        # Buscar provincia de entrega del partner (contacto activo en contexto)
        # TODO: en el contexto de una factura, el partner puede ser la dirección
        # de entrega. Aquí tomamos l10n_ar_state_id del partner si está adherida.
        delivery_state = partner.state_id if partner.state_id.l10n_ar_is_sircip else False

        # Determinar impuestos adicionales según campo 7
        extra_taxes = self.env["account.tax"]
        if delivery_state and aliquot is not None:
            campo7 = ""
            if ref and "campo7:" in ref:
                campo7 = ref.split("campo7:")[-1].strip()
            digit = self._get_sircip_campo7_digit(campo7, delivery_state)
            extra_taxes = self._get_sircip_extra_taxes(digit, delivery_state, base_tax)

        # Crear registro l10n_ar.partner.tax para la alícuota base (cacheo)
        self.env["l10n_ar.partner.tax"].create({
            "partner_id": partner.id,
            "tax_id": base_tax.id,
            "from_date": from_date,
            "to_date": to_date,
            "ref": ref,
        })

        return base_tax | extra_taxes

    def _get_sircip_extra_taxes(self, digit, delivery_state, base_tax):
        """Retorna los impuestos adicionales según el dígito del campo 7.

        Matriz de aplicación (fuente: pestaña "Aplicacion Códigos" del spreadsheet oficial):
        - Dígito 1: solo tasa básica (sin extra)
        - Dígito 2: sobrealícuota (1%)
        - Dígito 3: excluido — tratado como dígito 1 hasta resolución formal
        - Dígito 4/5: alícuota propia de la provincia (tasa estándar IIBB de esa provincia)

        TODO: validar la lógica exacta para dígitos 4 y 5 con la
        pestaña "Aplicacion Códigos" del spreadsheet oficial.
        """
        taxes = self.env["account.tax"]
        if digit == 2:
            sobretasa_ref = self.env.ref(
                "l10n_ar_sircip.tax_sircip_sobretasa", raise_if_not_found=False
            )
            if sobretasa_ref:
                company_sobretasa = self.env["account.tax"].search(
                    [
                        ("tax_group_id", "=", sobretasa_ref.tax_group_id.id),
                        ("company_id", "=", self.fiscal_position_id.company_id.id),
                        ("type_tax_use", "=", "sale"),
                    ],
                    limit=1,
                )
                taxes |= company_sobretasa
        elif digit in (4, 5):
            # TODO: obtener la alícuota propia de la provincia desde el padrón
            # o desde la posición fiscal estándar del partner para esa jurisdicción.
            _logger.warning(
                "SIRCIP campo7 dígito %s para provincia %s: lógica pendiente de implementación.",
                digit, delivery_state.name,
            )
        return taxes
