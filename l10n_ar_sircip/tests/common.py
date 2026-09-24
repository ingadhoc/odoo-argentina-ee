##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64

from odoo import Command, fields
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.addons.l10n_ar_sircip.hooks import _create_sircip_data_for_company
from odoo.addons.l10n_ar_sircip.models.account_fiscal_position_l10n_ar_tax import SIRCIP_CAMPO7_POSITION


def valid_cuit(prefix, number):
    """CUIT válido (con dígito verificador) a partir de un prefijo de 2 y un número de 8 dígitos."""
    while True:
        base = "%s%08d" % (prefix, number)
        dv = 11 - sum(int(d) * w for d, w in zip(base, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2))) % 11
        if dv != 10:
            return base + str(0 if dv == 11 else dv)
        number += 1


def campo7(digits):
    """Campo 7 del padrón: 24 jurisdicciones en '5' (no adherida, sin alta) salvo las indicadas, más el control.

    :param digits: dict {jurisdiction_code: dígito}
    """
    chars = ["5"] * 24 + ["0"]
    for jcode, digit in digits.items():
        chars[SIRCIP_CAMPO7_POSITION[jcode]] = str(digit)
    return "".join(chars)


class TestSircipCommon(TestArCommon):
    """Compañía RI con los datos SIRCIP del post_init_hook, un padrón del mes en curso y un cliente por caso.

    Provincias: Chaco (906) y Salta (917) adheridas; Corrientes (905) no adherida.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()
        cls.sircip_state = cls.env.ref("l10n_ar_sircip.state_ar_sircip")
        cls.chaco = cls.env.ref("base.state_ar_h")
        cls.salta = cls.env.ref("base.state_ar_a")
        cls.corrientes = cls.env.ref("base.state_ar_w")
        (cls.chaco | cls.salta).l10n_ar_is_sircip = True
        cls.corrientes.l10n_ar_is_sircip = False

        _create_sircip_data_for_company(cls.env, cls.company_ri, cls.sircip_state)
        cls.fiscal_position = cls.env.ref("l10n_ar_sircip.fiscal_position_sircip_%s" % cls.company_ri.id)
        cls.sircip_account = cls.env.ref("l10n_ar_sircip.account_sircip_%s" % cls.company_ri.id)
        cls.sircip_tag = cls.env.ref("l10n_ar_sircip.tag_perc_iibb_sircip_aplicada")
        cls.sale_journal = cls._create_journal("preprinted")
        cls.settlement_journal = cls.env["account.journal"].search(
            [("code", "=", "SIRC"), ("company_id", "=", cls.company_ri.id)], limit=1
        )

        # (clave, letra, provincia del domicilio, dígitos del campo 7). None en la letra = fuera del padrón.
        cases = [
            ("digit1", "T", cls.chaco, {"906": 1, "917": 1}),
            ("digit2", "F", cls.chaco, {"906": 2, "917": 1}),
            ("digit3", "F", cls.chaco, {"906": 3}),
            ("digit4", "F", cls.corrientes, {"905": 4}),
            ("digit5", "F", cls.corrientes, {"905": 5}),
            ("letter_a", "A", cls.chaco, {"906": 1}),
            ("letter_a_digit2", "A", cls.chaco, {"906": 2}),
            ("not_registered", None, cls.chaco, {}),
            ("not_registered_not_adhered", None, cls.corrientes, {}),
        ]
        cls.partners = {}
        cls.crc = {}
        rows = ["periodo,cuit,razon_social_contri,jurisdiccion_sede,crc,alicuota_unica_letra,campo7"]
        for number, (key, letter, state, digits) in enumerate(cases, start=10):
            vat = valid_cuit("30", 71000000 + number * 17)
            cls.partners[key] = cls.env["res.partner"].create(
                {
                    "name": "SIRCIP %s" % key,
                    "vat": vat,
                    "l10n_latam_identification_type_id": cls.env.ref("l10n_ar.it_cuit").id,
                    "l10n_ar_afip_responsibility_type_id": cls.env.ref("l10n_ar.res_IVARI").id,
                    "country_id": cls.env.ref("base.ar").id,
                    "state_id": state.id,
                }
            )
            if letter:
                cls.crc[key] = "%02d" % number
                rows.append(
                    "%s,%s,%s,906,%s,%s,%s"
                    % (cls.today.strftime("%Y%m"), vat, key, cls.crc[key], letter, campo7(digits))
                )
        month_start = cls.today.replace(day=1)
        cls.env["res.company.jurisdiction.padron"].create(
            {
                "company_id": cls.company_ri.id,
                "state_id": cls.sircip_state.id,
                "l10n_ar_padron_from_date": month_start,
                "l10n_ar_padron_to_date": fields.Date.end_of(month_start, "month"),
                "filename": "padron_sircip.txt",
                "file_padron": base64.b64encode("\n".join(rows).encode("latin-1")),
            }
        )

    @classmethod
    def _sircip_invoice(cls, partner, shipping=None, price_unit=1000.0, post=False):
        invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "partner_shipping_id": (shipping or partner).id,
                "journal_id": cls.sale_journal.id,
                "invoice_date": cls.today,
                "fiscal_position_id": cls.fiscal_position.id,
                "invoice_line_ids": [Command.create({"product_id": cls.product_iva_21.id, "price_unit": price_unit})],
            }
        )
        if post:
            invoice.action_post()
        return invoice

    @classmethod
    def _delivery(cls, partner, state):
        return cls.env["res.partner"].create(
            {"name": "Entrega %s" % state.name, "parent_id": partner.id, "type": "delivery", "state_id": state.id}
        )

    def _sircip_tax_names(self, move):
        taxes = move.invoice_line_ids.tax_ids.filtered("l10n_ar_sircip_record_type")
        return sorted(taxes.mapped("name"))

    def assert_sircip_invariants(self, move):
        """Lo que vale después de cualquier cálculo SIRCIP: el asiento cierra, ninguna línea de percepción
        queda en cero ni sin la cuenta y la etiqueta que usa el diario de liquidación."""
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)
        sircip_lines = move.line_ids.filtered("tax_line_id.l10n_ar_sircip_record_type")
        self.assertEqual(
            sorted(sircip_lines.tax_line_id.mapped("name")),
            self._sircip_tax_names(move),
            "cada percepción SIRCIP de las líneas genera su línea de impuesto",
        )
        for line in sircip_lines:
            self.assertTrue(line.balance, "línea de percepción en cero: %s" % line.name)
            self.assertEqual(line.account_id, self.sircip_account)
            self.assertIn(self.sircip_tag, line.tax_tag_ids)
