##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from dateutil.relativedelta import relativedelta
from odoo import _, api, models
from odoo.exceptions import UserError

from .account_tax import SIRCIP_RECORD_PERCEPTION, SIRCIP_RECORD_SURCHARGE
from .res_company_jurisdiction_padron import SIRCIP_LETTER_ALIQUOT

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

    def _l10n_ar_is_sircip(self):
        self.ensure_one()
        sircip_state = self._get_sircip_state()
        return bool(sircip_state) and self.default_tax_id.l10n_ar_state_id == sircip_state

    @api.constrains("webservice", "default_tax_id")
    def _check_webservice_available(self):
        """Extendemos para permitir webservice='padron' con la provincia ficticia SIRCIP."""
        non_sircip_padron = self.filtered(lambda r: not (r.webservice == "padron" and r._l10n_ar_is_sircip()))
        return super(AccountFiscalPositionL10nArTax, non_sircip_padron)._check_webservice_available()

    def _get_tax_from_ws(self, partner, date):
        if not self._l10n_ar_is_sircip():
            return super()._get_tax_from_ws(partner, date)
        return self._sircip_get_taxes(partner, date)

    def _sircip_get_taxes(self, partner, date):
        """Impuestos SIRCIP de una factura, según el padrón y la provincia de entrega.

        Reglas (planilla oficial "Aplicación Códigos" y Q&A CESSI de la Comisión Arbitral):
        - En el padrón: siempre "Percepción SIRCIP" con la alícuota de la letra, para cualquier dígito
          del campo 7. Con letra A (0%) no va nada en la factura: se declara como informativo en la DDJJ.
        - Dígito 2 en la provincia de entrega (adherida, sin alta): además, "Percepción SIRCIP por falta
          de alta en (provincia)" en una línea aparte.
        - Dígito 4 (no adherida, con alta): la percepción propia de la provincia la calcula su línea de
          posición fiscal, no SIRCIP.
        - Fuera del padrón: 2% "por no inscripto" solo si la entrega es en una provincia adherida.

        La provincia de entrega llega por contexto desde la factura o el pedido (``l10n_ar_delivery_partner_id``);
        sin ella se usa la del partner.
        """
        self.ensure_one()
        partner = partner.commercial_partner_id
        delivery_id = self.env.context.get("l10n_ar_delivery_partner_id")
        delivery = self.env["res.partner"].browse(delivery_id) if delivery_id else partner
        delivery_state = delivery.state_id or partner.state_id

        data = self._sircip_get_padron_data(partner, date)
        taxes = self.env["account.tax"]
        if not data["in_padron"]:
            return self.default_tax_id if delivery_state.l10n_ar_is_sircip else taxes
        if data["aliquot"]:
            taxes |= self._sircip_get_perception_tax(data["aliquot"])
        if self._get_sircip_campo7_digit(data["campo7"], delivery_state) == 2:
            taxes |= self._sircip_get_surcharge_tax(delivery_state)
        return taxes

    def _sircip_get_padron_data(self, partner, date):
        """Datos del padrón SIRCIP del partner para el mes de ``date``.

        Se consulta el padrón una vez por partner y mes, y se guarda en ``l10n_ar.partner.tax``
        (un solo registro por mes) con el CRC, la letra y el campo 7 en el ref. Los impuestos de cada
        factura se calculan a partir de ese registro, porque dependen de la provincia de entrega.
        """
        partner = partner.commercial_partner_id
        from_date = date + relativedelta(day=1)
        to_date = from_date + relativedelta(months=1, days=-1)
        cache = self.env["l10n_ar.partner.tax"].search(
            [
                ("partner_id", "=", partner.id),
                ("tax_id.tax_group_id", "=", self.default_tax_id.tax_group_id.id),
                ("from_date", "=", from_date),
                ("to_date", "=", to_date),
            ],
            limit=1,
        )
        if not cache:
            padron_file = self._search_padron_file(self._get_sircip_state(), date)
            if not padron_file:
                raise UserError(
                    _(
                        "No SIRCIP padron loaded for the period %(from)s to %(to)s. "
                        "Upload it at 'Accounting / Configuration / AFIP / Company Aliquot Padron' "
                        "using the 'SIRCIP' jurisdiction.",
                        **{"from": from_date, "to": to_date},
                    )
                )
            is_in_padron, aliquot, campo7, crc, letra = padron_file._get_sircip_aliquot(partner)
            if is_in_padron:
                tax = self._sircip_get_perception_tax(aliquot)
                ref = "SIRCIP | crc:%s | letra:%s | campo7:%s" % (crc, letra, campo7)
            else:
                tax = self.default_tax_id
                ref = "SIRCIP | no inscripto"
            cache = self.env["l10n_ar.partner.tax"].create(
                {
                    "partner_id": partner.id,
                    "tax_id": tax.id,
                    "from_date": from_date,
                    "to_date": to_date,
                    "ref": ref,
                }
            )
        return self._sircip_parse_ref(cache.ref)

    @api.model
    def _sircip_parse_ref(self, ref):
        """Lee el ref guardado por _sircip_get_padron_data: 'SIRCIP | crc:XX | letra:F | campo7:YYY'."""
        values = {}
        for part in (ref or "").split("|"):
            key, sep, value = part.partition(":")
            if sep:
                values[key.strip()] = value.strip()
        letra = values.get("letra", "")
        return {
            "in_padron": bool(letra),
            "crc": values.get("crc", ""),
            "letra": letra,
            "campo7": values.get("campo7", ""),
            "aliquot": SIRCIP_LETTER_ALIQUOT.get(letra, 0.0),
        }

    def _get_sircip_campo7_digit(self, campo7, delivery_state):
        """Dígito (1-5) del campo 7 para la provincia de entrega, o 0 si no se puede leer."""
        if not campo7 or not delivery_state:
            return 0
        pos = SIRCIP_CAMPO7_POSITION.get(delivery_state.jurisdiction_code or "")
        if pos is None or pos >= len(campo7):
            return 0
        try:
            return int(campo7[pos])
        except ValueError:
            return 0

    def _sircip_find_or_copy_tax(self, record_type, domain, values):
        """Busca un impuesto SIRCIP del tipo y compañía de la línea; si no existe, lo crea copiando la
        plantilla de ese tipo (creada por el post_init_hook), que trae cuentas y grupo."""
        company = self.fiscal_position_id.company_id
        Tax = self.env["account.tax"].with_context(active_test=False)
        base_domain = [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("tax_group_id", "=", self.default_tax_id.tax_group_id.id),
            ("l10n_ar_sircip_record_type", "=", record_type),
        ]
        tax = Tax.search(base_domain + domain, limit=1)
        if tax:
            if not tax.active:
                tax.active = True
            return tax
        template = Tax.search(base_domain, order="id", limit=1)
        if not template:
            raise UserError(_("SIRCIP tax template not found for company %(company)s.", company=company.display_name))
        return template.copy(default=dict(values, active=True))

    # Los nombres son la denominación que exige la Comisión Arbitral en la factura: no se traducen.
    def _sircip_get_perception_tax(self, aliquot):
        return self._sircip_find_or_copy_tax(
            SIRCIP_RECORD_PERCEPTION,
            [("amount", "=", aliquot)],
            {"name": "Percepción SIRCIP %.2f%%" % aliquot, "amount": aliquot},
        )

    def _sircip_get_surcharge_tax(self, state):
        return self._sircip_find_or_copy_tax(
            SIRCIP_RECORD_SURCHARGE,
            [("l10n_ar_state_id", "=", state.id)],
            {"name": "Percepción SIRCIP por falta de alta en %s" % state.name, "l10n_ar_state_id": state.id},
        )
