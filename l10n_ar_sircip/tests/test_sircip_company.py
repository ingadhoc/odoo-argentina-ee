##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command
from odoo.exceptions import UserError, ValidationError
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
        """Una compañía creada después de instalar el módulo se configura desde Ajustes. Si su plan no trae la
        cuenta de percepciones IIBB aplicadas (monotributo, custom), la cuenta SIRCIP se pide en Ajustes."""
        company = self.company_mono
        # Plan sin la cuenta de percepciones IIBB aplicadas
        self.env["ir.model.data"].search(
            [("module", "=", "account"), ("name", "=", "%s_ri_percepcion_iibb_tf_aplicada" % company.id)]
        ).unlink()
        with self.subTest("sin la opción, la compañía no tiene datos SIRCIP"):
            self.assertFalse(company.l10n_ar_sircip_agent)
            self.assertFalse(self._sircip_lines(company))
        with self.subTest("sin cuenta en el plan ni en Ajustes, guardar pide la cuenta"):
            with self.assertRaisesRegex(UserError, "SIRCIP Perception Account"):
                self._save_settings(company)
        account = self.env["account.account"].create(
            {
                "name": "Percepción SIRCIP",
                "code": "2.1.3.99.001",
                "account_type": "liability_current",
                "company_ids": [Command.link(company.id)],
            }
        )
        company.l10n_ar_sircip_account_id = account
        with self.subTest("con la cuenta en Ajustes, crea impuestos con esa cuenta, posición fiscal y grupo"):
            self._save_settings(company)
            self.assertTrue(company.l10n_ar_sircip_agent)
            templates = (
                self.env["account.tax"]
                .with_context(active_test=False)
                .search([("company_id", "=", company.id), ("l10n_ar_sircip_record_type", "!=", False)])
            )
            self.assertEqual(set(templates.mapped("l10n_ar_sircip_record_type")), {"1", "4", "5"})
            self.assertEqual(
                templates.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == "tax").account_id,
                account,
            )
            self.assertTrue(self.env.ref("l10n_ar_sircip.fiscal_position_sircip_%s" % company.id))
            self.assertEqual(templates.tax_group_id.l10n_ar_tribute_afip_code, "07")
        with self.subTest("con cuenta hermana en el plan (RI), la cuenta creada queda a la vista en Ajustes"):
            self.assertEqual(self.company_ri.l10n_ar_sircip_account_id, self.sircip_account)

    def test_sircip_line_is_a_padron_perception(self):
        """La línea SIRCIP de una posición fiscal solo puede ser una percepción que lee el archivo de padrón."""
        line = self.fiscal_position.l10n_ar_tax_ids.filtered(lambda x: x._l10n_ar_is_sircip())
        for values in ({"tax_type": "withholding"}, {"webservice": False}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                line.write(values)

    def test_sircip_state_is_not_a_province(self):
        """La provincia ficticia SIRCIP no se ofrece en los contactos ni se les puede asignar; en el padrón y el
        impuesto sí se ofrece."""
        State = self.env["res.country.state"]
        with self.subTest("el autocompletado no la ofrece"):
            self.assertNotIn(self.sircip_state.id, [x[0] for x in State.name_search("SIRCIP")])
        with self.subTest("en el padrón y el impuesto sí"):
            found = State.with_context(l10n_ar_sircip_show_state=True).name_search("SIRCIP")
            self.assertIn(self.sircip_state.id, [x[0] for x in found])
        with self.subTest("un contacto no puede tenerla como provincia"), self.assertRaises(ValidationError):
            self.partners["digit1"].state_id = self.sircip_state

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
