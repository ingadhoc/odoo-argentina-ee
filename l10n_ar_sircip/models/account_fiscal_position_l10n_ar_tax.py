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

# Nombre del impuesto marcador para operaciones excluidas (dígito 3 del campo 7).
# Fuente: CESSI Q&A — "Tipo de Registro 3: Excluido, no figura en factura pero sí en DJ"
_SIRCIP_EXCLUIDO_TAX_NAME = "SIRCIP Excluido"


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
                   Formato: "SIRCIP | crc:XX | letra:F | campo7:YYY"
        """
        self.ensure_one()
        sircip_state = self._get_sircip_state()
        padron_file = self._search_padron_file(sircip_state, date)
        if not padron_file:
            raise UserError(
                _(
                    "No SIRCIP padron loaded for the period %(from)s to %(to)s. "
                    "Upload it at 'Accounting / Configuration / AFIP / Company Aliquot Padron' "
                    "using the 'SIRCIP' jurisdiction."
                )
                % {"from": date, "to": to_date}
            )

        is_in_padron, aliquot, campo7, crc, letra = padron_file._get_sircip_aliquot(partner)

        if not is_in_padron:
            return None, _("SIRCIP Non-Registered (not found in padron)")

        ref = "SIRCIP | crc:%s | letra:%s | campo7:%s" % (crc, letra, campo7)
        return aliquot, ref

    def _get_delivery_state(self, partner):
        """Obtiene la provincia de entrega para el cálculo del campo 7.

        Prioridad:
        1. partner_shipping_id de la factura activa en el contexto
        2. partner_shipping_id pasado explícitamente en el contexto
        3. state_id del propio partner

        Solo retorna la provincia si está adherida a SIRCIP (l10n_ar_is_sircip=True).
        """
        delivery_partner = None

        # Buscar la factura activa en el contexto para obtener partner_shipping_id
        ctx = self.env.context
        if ctx.get("partner_shipping_id"):
            delivery_partner = self.env["res.partner"].browse(ctx["partner_shipping_id"])
        elif ctx.get("active_model") == "account.move" and ctx.get("active_id"):
            move = self.env["account.move"].browse(ctx["active_id"])
            if move.exists() and move.partner_shipping_id:
                delivery_partner = move.partner_shipping_id

        # Usar la provincia del delivery partner si está adherida a SIRCIP
        if delivery_partner and delivery_partner.state_id and delivery_partner.state_id.l10n_ar_is_sircip:
            return delivery_partner.state_id

        # Fallback al state_id del propio partner
        if partner.state_id and partner.state_id.l10n_ar_is_sircip:
            return partner.state_id

        return False

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

    def _sircip_tax_name(self, aliquot, letra, delivery_state):
        """Genera el nombre del impuesto SIRCIP dinámico.

        Formato: 'SIRCIP [Provincia] X.XX% (Letra)'
        Ejemplo: 'SIRCIP Chaco 3.00% (T)'
        """
        province = delivery_state.name if delivery_state else ""
        if province:
            return "SIRCIP %s %.2f%% (%s)" % (province, aliquot, letra)
        return "SIRCIP %.2f%% (%s)" % (aliquot, letra)

    def _ensure_sircip_tax(self, aliquot, letra, delivery_state):
        """Busca o crea un impuesto SIRCIP con el nombre que incluye provincia y letra.

        Busca primero por nombre exacto (con provincia). Si no encuentra,
        busca por monto (compatibilidad con impuestos creados con nombre anterior).
        Excluye el impuesto 'SIRCIP Excluido' (es un marcador, no una alícuota real).
        """
        name = self._sircip_tax_name(aliquot, letra, delivery_state)
        domain = self._get_tax_domain()
        # Filtrar siempre por grupo SIRCIP para no mezclar con impuestos provinciales estándar.
        amount_domain = domain + [
            ("amount", "=", aliquot),
            ("name", "!=", _SIRCIP_EXCLUIDO_TAX_NAME),
            ("tax_group_id.name", "=", "SIRCIP"),
        ]

        # 1. Buscar por nombre exacto (con provincia y letra)
        tax = (
            self.env["account.tax"]
            .with_context(active_test=False)
            .search(amount_domain + [("name", "=", name)], limit=1)
        )
        # 2. Fallback por monto (impuestos SIRCIP con nombre anterior o sin provincia)
        if not tax:
            tax = self.env["account.tax"].with_context(active_test=False).search(amount_domain, limit=1)

        if tax:
            if not tax.active:
                tax.active = True
            return tax

        # 3. Crear con el nuevo nombre y la jurisdicción de entrega como estado fiscal.
        # Usamos copy() para heredar repartition_line_ids del impuesto base, y luego
        # write() explícito para garantizar que la jurisdicción queda correctamente asignada.
        sircip_state = self._get_sircip_state()
        new_tax = self.default_tax_id.copy(
            default={
                "sequence": 10,
                "amount": aliquot,
                "active": True,
                "name": name,
            }
        )
        state_id = delivery_state.id if delivery_state else (sircip_state.id if sircip_state else False)
        if state_id:
            new_tax.write({"l10n_ar_state_id": state_id})
        return new_tax

    def _get_sircip_excluido_tax(self):
        """Retorna el impuesto marcador 'SIRCIP Excluido' (0%, dígito 3 del campo 7).

        Este impuesto se agrega a la factura a $0 para que el TXT de DDJJ lo detecte
        y lo reporte como Tipo de Registro = 3 (Excluido).
        Fuente: CESSI Q&A — la operación no impacta la factura pero sí debe declararse en DJ.
        """
        return self.env["account.tax"].search(
            [
                ("name", "=", _SIRCIP_EXCLUIDO_TAX_NAME),
                ("tax_group_id.name", "=", "SIRCIP"),
                ("company_id", "=", self.fiscal_position_id.company_id.id),
                ("type_tax_use", "=", "sale"),
            ],
            limit=1,
        )

    def _get_tax_from_ws(self, partner, date):
        """Override para SIRCIP: aplica los impuestos correctos según el dígito del campo 7.

        Dígitos del campo 7 (leídos para la provincia de entrega):
        - 1: solo tasa básica SIRCIP
        - 2: tasa básica + sobrealícuota 1% ("falta de alta en jurisdicción")
        - 3: operación excluida — agrega impuesto marcador a $0, declarar en DJ tipo 3
        - 4/5: tasa básica + alícuota propia de la provincia (no adherida al SIRCIP)
        """
        sircip_state = self._get_sircip_state()
        if not (sircip_state and self.default_tax_id.l10n_ar_state_id == sircip_state):
            return super()._get_tax_from_ws(partner, date)

        from_date = date + relativedelta(day=1)
        to_date = from_date + relativedelta(days=-1, months=+1)

        aliquot, ref = self._get_sircip_padron_data(partner, from_date, to_date)

        # Extraer letra del ref para el naming del impuesto
        letra = ""
        if ref and "letra:" in ref:
            letra = ref.split("letra:")[-1].split("|")[0].strip()

        # Determinar la provincia de entrega y el dígito del campo 7
        delivery_state = self._get_delivery_state(partner)
        digit = 0
        if delivery_state and aliquot is not None:
            campo7 = ref.split("campo7:")[-1].strip() if "campo7:" in ref else ""
            digit = self._get_sircip_campo7_digit(campo7, delivery_state)

        if digit == 3:
            # Excluido: agrega impuesto marcador a $0 en la factura.
            # Nada se cobra al cliente pero la operación debe declararse en DJ tipo 3.
            # Fuente: CESSI Q&A — "no es necesario incorporar nada en la factura,
            # declarar con Tipo de Registro = 3-Excluido"
            tax_to_cache = self._get_sircip_excluido_tax()
            taxes_to_return = tax_to_cache
        else:
            # Flujo normal: calcular impuesto base + extras
            if aliquot is None:
                tax_to_cache = self.default_tax_id
            else:
                tax_to_cache = self._ensure_sircip_tax(aliquot, letra, delivery_state)
            extra_taxes = self._get_sircip_extra_taxes(digit, delivery_state, partner, date)
            taxes_to_return = tax_to_cache | extra_taxes

        # Cachear en l10n_ar.partner.tax para evitar re-consultar el padrón
        if tax_to_cache:
            self.env["l10n_ar.partner.tax"].create(
                {
                    "partner_id": partner.id,
                    "tax_id": tax_to_cache.id,
                    "from_date": from_date,
                    "to_date": to_date,
                    "ref": ref,
                }
            )

        return taxes_to_return

    def _get_sircip_extra_taxes(self, digit, delivery_state, partner=None, date=None):
        """Impuestos adicionales según el dígito del campo 7.

        | Dígito | Significado              | Extra tax                        |
        |--------|--------------------------|----------------------------------|
        |   1    | Adherida, inscripto      | Ninguno                          |
        |   2    | Adherida, sin alta       | Sobrealícuota 1% (falta de alta) |
        |   4/5  | No adherida, con/sin alta| Alícuota provincial propia       |
        Nota: dígito 3 (Excluido) es manejado directamente en _get_tax_from_ws.
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

        # 3. Not found: raise with clear instructions
        raise UserError(
            _(
                "SIRCIP — double rate (digit 4/5) for province %(province)s: "
                "the province's own rate was not found.\n\n"
                "To resolve this, use one of the following options:\n"
                "1) Set up a fiscal position with an IIBB perception for %(province)s "
                "(using %(province)s webservice or padron) for the same company. "
                "The system will query it automatically when invoicing.\n"
                "2) Enter the rate manually on the contact under "
                "Accounting → Perceptions/Withholdings for the "
                "%(province)s tax for period %(from_date)s–%(to_date)s.",
                province=delivery_state.name,
                from_date=from_date,
                to_date=to_date,
            )
        )
