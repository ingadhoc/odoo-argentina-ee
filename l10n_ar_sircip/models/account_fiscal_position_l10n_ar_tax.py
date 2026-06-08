##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging

from dateutil.relativedelta import relativedelta
from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Posición de cada jurisdicción en el campo 7 del padrón SIRCIP.
# El campo 7 tiene 25 chars numéricos. Se lee de DERECHA a IZQUIERDA:
#   - índice 24 (rightmost) = siempre '0', descartar
#   - las posiciones 1-24 (de derecha a izquierda) corresponden a
#     jurisdicciones 901-924 en orden numérico ascendente
# Fórmula: índice (0-based) = 924 - jurisdiction_code
# Fuente: doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf
SIRCIP_CAMPO7_POSITION = {
    "901": 23,  # CABA (code C)
    "902": 22,  # Buenos Aires (code B)
    "903": 21,  # Catamarca (code K)
    "904": 20,  # Córdoba (code X)
    "905": 19,  # Corrientes (code W)
    "906": 18,  # Chaco (code H)
    "907": 17,  # Chubut (code U)
    "908": 16,  # Entre Ríos (code E)
    "909": 15,  # Formosa (code P)
    "910": 14,  # Jujuy (code Y)
    "911": 13,  # La Pampa (code L)
    "912": 12,  # La Rioja (code F)
    "913": 11,  # Mendoza (code M)
    "914": 10,  # Misiones (code N)
    "915": 9,  # Neuquén (code Q)
    "916": 8,  # Río Negro (code R)
    "917": 7,  # Salta (code A)
    "918": 6,  # San Juan (code J)
    "919": 5,  # San Luis (code D)
    "920": 4,  # Santa Cruz (code Z)
    "921": 3,  # Santa Fe (code S)
    "922": 2,  # Santiago del Estero (code G)
    "923": 1,  # Tierra del Fuego (code V)
    "924": 0,  # Tucumán (code T)
    # índice 24 = siempre '0', se descarta
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
                lambda r: not (r.webservice == "padron" and r.default_tax_id.l10n_ar_state_id == sircip_state)
            )
        else:
            non_sircip_padron = self
        return super(AccountFiscalPositionL10nArTax, non_sircip_padron)._check_webservice_available()

    def _get_padron_data(self, partner, date, to_date):
        """Override: cuando el impuesto apunta a la provincia ficticia SIRCIP,
        delegar al flujo SIRCIP en lugar del flujo estándar."""
        sircip_state = self._get_sircip_state()
        if sircip_state and self.default_tax_id.l10n_ar_state_id == sircip_state:
            return self._get_sircip_padron_data(partner, date, to_date)
        return super()._get_padron_data(partner, date, to_date)

    def _get_sircip_padron_data(self, partner, date, to_date):
        """Obtiene alícuota y CRC del padrón SIRCIP para el período dado.

        :return: (aliquot_or_None, ref_string)
                 - aliquot_or_None: float o None (None → usar default_tax_id = No Inscripto)
                 - ref_string: trazabilidad almacenada en l10n_ar.partner.tax.ref
        """
        self.ensure_one()
        sircip_state = self._get_sircip_state()
        padron_file = self._search_padron_file(sircip_state, date)
        if not padron_file:
            raise UserError(
                _(
                    "No hay padrón SIRCIP cargado para el período %(from)s a %(to)s. "
                    "Súbalo en 'Contabilidad / Configuración / AFIP / Padrón de Alícuotas por Compañía' "
                    "usando la jurisdicción 'SIRCIP'."
                )
                % {"from": date, "to": to_date}
            )

        is_in_padron, aliquot, campo7, crc = padron_file._get_sircip_aliquot(partner)

        if not is_in_padron:
            return None, "SIRCIP No Inscripto (no figura en padrón)"

        ref = "SIRCIP | crc:%s | campo7:%s" % (crc, campo7)
        return aliquot, ref

    def _get_sircip_campo7_digit(self, campo7, delivery_state):
        """Obtiene el dígito del campo 7 para la provincia de entrega dada.

        :param campo7: string de 25 posiciones del padrón SIRCIP
        :param delivery_state: res.country.state del domicilio de entrega
        :return: int (dígito 0-5) o 0 si la provincia no tiene posición definida
        """
        if not campo7 or not delivery_state:
            return 0
        jcode = delivery_state.jurisdiction_code or ""
        pos = SIRCIP_CAMPO7_POSITION.get(jcode)
        if pos is None or pos >= len(campo7):
            return 0
        try:
            return int(campo7[pos])
        except (ValueError, IndexError):
            return 0

    def _get_tax_from_ws(self, partner, date):
        """Override para SIRCIP: cuando el dígito del campo 7 lo requiere,
        retorna múltiples impuestos (base + sobrealícuota)."""
        sircip_state = self._get_sircip_state()
        if not (sircip_state and self.default_tax_id.l10n_ar_state_id == sircip_state):
            return super()._get_tax_from_ws(partner, date)

        from_date = date + relativedelta(day=1)
        to_date = from_date + relativedelta(days=-1, months=+1)

        aliquot, ref = self._get_sircip_padron_data(partner, from_date, to_date)

        if aliquot is None:
            base_tax = self.default_tax_id
        else:
            base_tax = self._ensure_tax(aliquot)

        # Buscar provincia de entrega del partner
        delivery_state = False
        if partner.state_id and partner.state_id.l10n_ar_is_sircip:
            delivery_state = partner.state_id

        # Determinar impuestos adicionales según campo 7
        extra_taxes = self.env["account.tax"]
        if delivery_state and aliquot is not None:
            campo7 = ref.split("campo7:")[-1].strip() if "campo7:" in ref else ""
            digit = self._get_sircip_campo7_digit(campo7, delivery_state)
            extra_taxes = self._get_sircip_extra_taxes(digit, delivery_state, partner, date)

        # Cachear alícuota base en l10n_ar.partner.tax
        self.env["l10n_ar.partner.tax"].create(
            {
                "partner_id": partner.id,
                "tax_id": base_tax.id,
                "from_date": from_date,
                "to_date": to_date,
                "ref": ref,
            }
        )

        return base_tax | extra_taxes

    def _get_sircip_extra_taxes(self, digit, delivery_state, partner=None, date=None):
        """Impuestos adicionales según el dígito del campo 7.

        Dígito 2: sobrealícuota SIRCIP (1%)
        Dígito 4/5: alícuota propia de la provincia (SIRCIP + tasa provincial)
        Resto: sin impuestos extra
        """
        taxes = self.env["account.tax"]
        if digit == 2:
            sobretasa = self.env["account.tax"].search(
                [
                    ("name", "ilike", "Sobre Alícuota"),
                    ("tax_group_id.name", "=", "SIRCIP"),
                    ("company_id", "=", self.fiscal_position_id.company_id.id),
                    ("type_tax_use", "=", "sale"),
                ],
                limit=1,
            )
            taxes |= sobretasa
        elif digit in (4, 5):
            provincial_tax = self._get_sircip_provincial_tax(delivery_state, partner, date)
            taxes |= provincial_tax
        return taxes

    def _get_sircip_provincial_tax(self, delivery_state, partner, date):
        """Obtiene la alícuota propia de la provincia para dígitos 4/5 del campo 7.

        La "alícuota propia" es la tasa IIBB estándar de la provincia para CM.
        Se busca en orden:

        1. l10n_ar.partner.tax existente para esa provincia/período (ya cacheado
           desde ARBA, AGIP, Rentas Córdoba u otro webservice anterior).
        2. account.fiscal.position.l10n_ar_tax con esa jurisdicción en la misma
           empresa → llama al webservice correspondiente para obtener la tasa.
        3. Si no se encuentra: UserError con instrucciones para configurar.

        :param delivery_state: res.country.state del domicilio de entrega
        :param partner: res.partner
        :param date: date de la factura
        :return: account.tax recordset (puede ser vacío si la búsqueda no aplica)
        """
        if not delivery_state or not partner or not date:
            return self.env["account.tax"]

        from_date = date + relativedelta(day=1)
        to_date = from_date + relativedelta(days=-1, months=+1)
        company = self.fiscal_position_id.company_id

        # 1. Buscar en partner.tax existente para esa provincia y período
        existing = self.env["l10n_ar.partner.tax"].search(
            [
                ("partner_id", "=", partner.id),
                ("tax_id.l10n_ar_state_id", "=", delivery_state.id),
                ("tax_id.tax_group_id.name", "!=", "SIRCIP"),
                ("tax_id.type_tax_use", "=", "sale"),
                "|",
                ("from_date", "=", False),
                ("from_date", "<=", to_date),
                "|",
                ("to_date", "=", False),
                ("to_date", ">=", from_date),
            ],
            limit=1,
            order="from_date desc",
        )
        if existing:
            _logger.info(
                "SIRCIP doble alícuota: usando partner.tax existente '%s' para provincia %s",
                existing.tax_id.name,
                delivery_state.name,
            )
            return existing.tax_id

        # 2. Buscar una línea de posición fiscal con esa jurisdicción y llamar al WS
        fiscal_line = self.env["account.fiscal.position.l10n_ar_tax"].search(
            [
                ("default_tax_id.l10n_ar_state_id", "=", delivery_state.id),
                ("default_tax_id.tax_group_id.name", "!=", "SIRCIP"),
                ("tax_type", "=", "perception"),
                ("fiscal_position_id.company_id", "=", company.id),
                ("webservice", "!=", False),
            ],
            limit=1,
        )
        if fiscal_line:
            _logger.info(
                "SIRCIP doble alícuota: consultando webservice '%s' para provincia %s",
                fiscal_line.webservice,
                delivery_state.name,
            )
            return fiscal_line._get_missing_taxes(partner, date)

        # 3. No encontrado: error con instrucciones claras
        raise UserError(
            _(
                "SIRCIP — doble alícuota (dígito 4/5) para la provincia %(province)s: "
                "no se encontró la alícuota propia de la provincia.\n\n"
                "Para resolverlo, alguna de estas opciones:\n"
                "1) Configure una posición fiscal con percepción de IIBB para %(province)s "
                "(usando el webservice de %(province)s o padrón) con la misma empresa. "
                "Al facturar, el sistema la consultará automáticamente.\n"
                "2) Ingrese manualmente la alícuota del contacto en la pestaña "
                "Contabilidad → Percepciones/Retenciones para el impuesto "
                "de %(province)s y el período %(from_date)s–%(to_date)s.",
                province=delivery_state.name,
                from_date=from_date,
                to_date=to_date,
            )
        )
