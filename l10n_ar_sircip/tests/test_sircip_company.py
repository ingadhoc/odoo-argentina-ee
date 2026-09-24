##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command
from odoo.tests import tagged

from .common import TestSircipCommon


@tagged("post_install", "-at_install")
class TestSircipCompany(TestSircipCommon):
    def _save_settings(self, company, agent=True):
        settings = self.env["res.config.settings"].with_company(company).create({"l10n_ar_sircip_agent": agent})
        settings.execute()

    def _sircip_lines(self, company):
        return self.env["account.fiscal.position.l10n_ar_tax"].search(
            [
                ("fiscal_position_id.company_id", "=", company.id),
                ("default_tax_id.l10n_ar_sircip_record_type", "!=", False),
            ]
        )

    def test_new_company_from_settings(self):
        """Una compañía creada después de instalar el módulo se configura desde Ajustes: el hook solo alcanza a las
        que existían al instalar."""
        company = self.company_mono
        with self.subTest("sin la opción, la compañía no tiene datos SIRCIP"):
            self.assertFalse(company.l10n_ar_sircip_agent)
            self.assertFalse(self._sircip_lines(company))
        with self.subTest("activar 'Agente de percepción SIRCIP' crea impuestos, posición fiscal y grupo"):
            self._save_settings(company)
            self.assertTrue(company.l10n_ar_sircip_agent)
            templates = (
                self.env["account.tax"]
                .with_context(active_test=False)
                .search([("company_id", "=", company.id), ("l10n_ar_sircip_record_type", "!=", False)])
            )
            self.assertEqual(set(templates.mapped("l10n_ar_sircip_record_type")), {"1", "4", "5"})
            self.assertTrue(self.env.ref("l10n_ar_sircip.fiscal_position_sircip_%s" % company.id))
            self.assertEqual(templates.tax_group_id.l10n_ar_tribute_afip_code, "07")

    def test_fiscal_positions_created_later(self):
        """Las posiciones fiscales con percepciones creadas después reciben la línea SIRCIP al guardar los Ajustes,
        y avisan mientras no la tengan o si tienen percepciones de provincias que ya pasaron a SIRCIP."""
        buenos_aires = self.tax_perc_iibb.l10n_ar_state_id
        fiscal_position = self.env["account.fiscal.position"].create(
            {
                "name": "Percepciones %s" % buenos_aires.name,
                "company_id": self.company_ri.id,
                "l10n_ar_tax_ids": [
                    Command.create({"default_tax_id": self.tax_perc_iibb.id, "tax_type": "perception"})
                ],
            }
        )
        with self.subTest("una posición fiscal nueva con percepciones avisa que le falta la línea SIRCIP"):
            self.assertIn("SIRCIP line", fiscal_position.l10n_ar_sircip_warning)
        with self.subTest("guardar los Ajustes agrega la línea SIRCIP y el aviso desaparece"):
            self._save_settings(self.company_ri)
            self.assertEqual(len(fiscal_position.l10n_ar_tax_ids.filtered(lambda x: x._l10n_ar_is_sircip())), 1)
            self.assertFalse(fiscal_position.l10n_ar_sircip_warning)
        with self.subTest("si la provincia de una percepción se adhiere, avisa que hay que sacar esa línea"):
            buenos_aires.l10n_ar_is_sircip = True
            fiscal_position.invalidate_recordset(["l10n_ar_sircip_warning"])
            self.assertIn(buenos_aires.name, fiscal_position.l10n_ar_sircip_warning)
        with self.subTest("guardar de nuevo no duplica nada"):
            lines_before = self._sircip_lines(self.company_ri)
            self._save_settings(self.company_ri)
            self.assertEqual(self._sircip_lines(self.company_ri), lines_before)
            self.assertEqual(
                self.env["account.journal"].search_count(
                    [("code", "=", "SIRC"), ("company_id", "=", self.company_ri.id)]
                ),
                len(self.settlement_journal),
            )
