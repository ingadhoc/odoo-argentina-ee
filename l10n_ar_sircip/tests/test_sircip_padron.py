##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64
import io
import zipfile

from dateutil.relativedelta import relativedelta
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common

# Letters F, A, X, B and V; {period} is filled with the padron month
SAMPLE_PADRON = (
    "periodo,cuit,razon_social_contri,jurisdiccion_sede,crc,alicuota_unica_letra,campo7\n"
    "{period},34111111113,EMPRESA F,922,25,F,5214252222222225522522550\n"
    "{period},34222222224,EMPRESA A,904,84,A,5224252222222225522512550\n"
    "{period},34333333335,EMPRESA X,901,34,X,5225252122222225522522540\n"
    "{period},34444444446,EMPRESA B,902,14,B,5224242222222125522512440\n"
    "{period},34555555557,EMPRESA V SOBRETASA,921,78,V,4214241111111114411411440\n"
)


class TestSircipPadron(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # SIRCIP data only exists for AR-chart companies: switch to company_ri.
        company_ri = cls.env.ref("base.company_ri")
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[company_ri.id]))
        cls.sircip_state = cls.env.ref("l10n_ar_sircip.state_ar_sircip")
        cls.month_start = fields.Date.today().replace(day=1)
        cls.month_end = fields.Date.end_of(cls.month_start, "month")
        cls.padron = cls.env["res.company.jurisdiction.padron"].create(
            {
                "company_id": cls.env.company.id,
                "state_id": cls.sircip_state.id,
                "l10n_ar_padron_from_date": cls.month_start,
                "l10n_ar_padron_to_date": cls.month_end,
                "filename": "test_padron.txt",
                "file_padron": cls._padron_file(cls.month_start),
            }
        )

    @classmethod
    def _padron_file(cls, date, zipped=False):
        content = SAMPLE_PADRON.format(period=date.strftime("%Y%m")).encode("latin-1")
        if zipped:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as zip_file:
                for name in zipped:
                    zip_file.writestr(name, content)
            content = buffer.getvalue()
        return base64.b64encode(content).decode()

    def _new_padron(self, file_padron):
        return self.env["res.company.jurisdiction.padron"].create(
            {
                "company_id": self.env.company.id,
                "state_id": self.sircip_state.id,
                "l10n_ar_padron_from_date": self.month_start,
                "l10n_ar_padron_to_date": self.month_end,
                "filename": "padron.txt",
                "file_padron": file_padron,
            }
        )

    def test_padron_period_is_the_padron_month(self):
        """The file period must be the padron month: next month's file is published earlier."""
        next_month = self.month_start + relativedelta(months=1)
        with self.assertRaisesRegex(ValidationError, next_month.strftime("%Y%m")):
            self._new_padron(self._padron_file(next_month))

    def test_padron_zip(self):
        """The padron can be loaded as a ZIP holding a single file."""
        padron = self._new_padron(self._padron_file(self.month_start, zipped=["padron.txt"]))
        self.assertEqual(padron._get_sircip_aliquot(self._make_partner("34333333335"))[1], 5.0)
        with self.assertRaises(ValidationError):
            self._new_padron(self._padron_file(self.month_start, zipped=["a.txt", "b.txt"]))

    def test_check_state_id_allows_sircip_province(self):
        """check_state_id accepts the SIRCIP pseudo-province (setUpClass already created one)."""
        self.assertTrue(self.padron.id)

    def test_check_state_id_rejects_non_sircip(self):
        """check_state_id rejects provinces other than SIRCIP and ARBA/SF."""
        state_cordoba = self.env.ref("base.state_ar_x")
        with self.assertRaises(ValidationError):
            self.env["res.company.jurisdiction.padron"].create(
                {
                    "company_id": self.env.company.id,
                    "state_id": state_cordoba.id,
                    "l10n_ar_padron_from_date": self.month_start,
                    "l10n_ar_padron_to_date": self.month_end,
                    "filename": "test.txt",
                    "file_padron": base64.b64encode(b"dummy").decode(),
                }
            )

    def _make_partner(self, vat):
        return self.env["res.partner"].create(
            {
                "name": "Test Partner %s" % vat,
                "vat": vat,
                "l10n_latam_identification_type_id": self.env.ref("l10n_ar.it_cuit").id,
            }
        )

    def test_aliquot_letra_f(self):
        """Letter F -> 0.30%."""
        partner = self._make_partner("34111111113")
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 0.30)
        self.assertEqual(crc, "25")
        self.assertEqual(len(campo7), 25)

    def test_aliquot_letra_a(self):
        """Letter A -> 0.00%."""
        partner = self._make_partner("34222222224")
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 0.00)

    def test_aliquot_letra_x(self):
        """Letter X -> 5.00%."""
        partner = self._make_partner("34333333335")
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 5.00)

    def test_aliquot_letra_b(self):
        """Letter B -> 0.01%."""
        partner = self._make_partner("34444444446")
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertTrue(is_in)
        self.assertAlmostEqual(aliquot, 0.01)

    def test_cuit_not_in_padron(self):
        """A CUIT not in the padron returns is_in_padron=False."""
        partner = self._make_partner("34666666668")
        is_in, aliquot, campo7, crc, letra = self.padron._get_sircip_aliquot(partner)
        self.assertFalse(is_in)
        self.assertEqual(aliquot, 0.0)
        self.assertEqual(campo7, "")

    def test_campo7_length(self):
        """Field 7 read from the padron is exactly 25 chars long."""
        partner = self._make_partner("34111111113")
        _, _, campo7, _, _ = self.padron._get_sircip_aliquot(partner)
        self.assertEqual(len(campo7), 25, "Field 7 must be 25 chars long")

    def test_campo7_rightmost_is_zero(self):
        """The rightmost char of field 7 is always '0'."""
        partner = self._make_partner("34111111113")
        _, _, campo7, _, _ = self.padron._get_sircip_aliquot(partner)
        self.assertEqual(campo7[-1], "0", "The rightmost char of field 7 must be '0'")

    def test_fiscal_position_has_correct_configuration(self):
        """The SIRCIP fiscal position is auto-applied: auto_apply, country AR, sequence 9999 (after the
        provincial ones) and the IVA RI responsibility."""
        ivari = self.env.ref("l10n_ar.res_IVARI", raise_if_not_found=False)
        self.assertTrue(ivari, "l10n_ar.res_IVARI not found: check that l10n_ar is installed")

        fp = self.env["account.fiscal.position"].search(
            [("name", "=", "Percepción - SIRCIP"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        self.assertTrue(
            fp,
            "Fiscal position 'Percepción - SIRCIP' not found: the post_init_hook creates it for AR-chart companies",
        )

        self.assertTrue(fp.auto_apply, "auto_apply must be True to apply on invoices")
        self.assertEqual(fp.sequence, 9999, "sequence must be 9999 (the last one)")
        self.assertEqual(fp.country_id, self.env.ref("base.ar"), "country_id must be AR")
        self.assertIn(
            ivari,
            fp.l10n_ar_afip_responsibility_type_ids,
            "l10n_ar_afip_responsibility_type_ids must include IVA RI: "
            "otherwise it is not auto-applied to RI customers",
        )

    def test_hook_tax_templates(self):
        """The hook leaves one template per DDJJ record type, with the settlement journal account and tag, in a
        group with the AFIP IIBB perception tribute code (07)."""
        templates = (
            self.env["account.tax"]
            .with_context(active_test=False)
            .search([("company_id", "=", self.env.company.id), ("l10n_ar_sircip_record_type", "!=", False)])
        )
        self.assertEqual(set(templates.mapped("l10n_ar_sircip_record_type")), {"1", "4", "5"})
        tag = self.env.ref("l10n_ar_sircip.tag_perc_iibb_sircip_aplicada")
        for tax in templates:
            tax_line = tax.invoice_repartition_line_ids.filtered(lambda r: r.repartition_type == "tax")
            self.assertTrue(tax_line.account_id, "%s has no account" % tax.name)
            self.assertIn(tag, tax_line.tag_ids)
        self.assertEqual(templates.tax_group_id.l10n_ar_tribute_afip_code, "07")
