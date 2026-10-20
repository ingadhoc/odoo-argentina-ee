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
        """A company created after install is set up from Settings; if its chart lacks the applied IIBB
        perception account, Settings asks for the SIRCIP account."""
        company = self.company_mono
        # Chart without the applied IIBB perception account
        self.env["ir.model.data"].search(
            [("module", "=", "account"), ("name", "=", "%s_ri_percepcion_iibb_tf_aplicada" % company.id)]
        ).unlink()
        with self.subTest("without the option, the company has no SIRCIP data"):
            self.assertFalse(company.l10n_ar_sircip_agent)
            self.assertFalse(self._sircip_lines(company))
        with self.subTest("with no account in the chart nor in Settings, saving asks for it"):
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
        with self.subTest("with the Settings account, it creates taxes on that account, fiscal position and group"):
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
        with self.subTest("with a sibling account in the chart (RI), the created account shows in Settings"):
            self.assertEqual(self.company_ri.l10n_ar_sircip_account_id, self.sircip_account)

    def test_sircip_line_is_a_padron_perception(self):
        """SIRCIP lines, and every line of the SIRCIP fiscal position, can only be perceptions read from the padron file."""
        line = self.fiscal_position.l10n_ar_tax_ids.filtered(lambda x: x._l10n_ar_is_sircip())
        for values in ({"tax_type": "withholding"}, {"webservice": False}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                line.write(values)
        with self.subTest("the SIRCIP fiscal position only accepts padron perceptions"):
            with self.assertRaises(ValidationError):
                self.fiscal_position.l10n_ar_tax_ids = [
                    Command.create({"default_tax_id": self.tax_perc_iibb.id, "tax_type": "perception"})
                ]

    def test_sircip_state_is_not_a_province(self):
        """The SIRCIP pseudo-province is neither offered nor assignable on contacts, but it is on the padron
        and the tax."""
        State = self.env["res.country.state"]
        with self.subTest("autocomplete does not offer it"):
            self.assertNotIn(self.sircip_state.id, [x[0] for x in State.name_search("SIRCIP")])
        with self.subTest("the padron and the tax do"):
            found = State.with_context(l10n_ar_sircip_show_state=True).name_search("SIRCIP")
            self.assertIn(self.sircip_state.id, [x[0] for x in found])
        with self.subTest("a contact cannot have it as province"), self.assertRaises(ValidationError):
            self.partners["digit1"].state_id = self.sircip_state

    def test_fiscal_positions_created_later(self):
        """On agent companies, perception fiscal positions created or edited later get the SIRCIP line, and warn
        while they hold perceptions of adhered provinces."""
        buenos_aires = self.tax_perc_iibb.l10n_ar_state_id
        perception = [Command.create({"default_tax_id": self.tax_perc_iibb.id, "tax_type": "perception"})]
        fiscal_position = self.env["account.fiscal.position"].create(
            {
                "name": "Percepciones %s" % buenos_aires.name,
                "company_id": self.company_ri.id,
                "state_ids": [Command.set(buenos_aires.ids)],
                "l10n_ar_tax_ids": perception,
            }
        )
        with self.subTest("a new perception fiscal position gets the SIRCIP line"):
            self.assertEqual(len(fiscal_position.l10n_ar_tax_ids.filtered(lambda x: x._l10n_ar_is_sircip())), 1)
            self.assertFalse(fiscal_position.l10n_ar_sircip_warning)
        with self.subTest("adding a perception to an existing fiscal position also adds it"):
            other = self.env["account.fiscal.position"].create(
                {"name": "Sin percepciones", "company_id": self.company_ri.id}
            )
            self.assertFalse(other.l10n_ar_tax_ids, "without perceptions there is nothing to add")
            other.l10n_ar_tax_ids = perception
            self.assertEqual(len(other.l10n_ar_tax_ids.filtered(lambda x: x._l10n_ar_is_sircip())), 1)
        with self.subTest("if the province of a perception adheres, it warns to remove that line"):
            buenos_aires.l10n_ar_is_sircip = True
            fiscal_position.invalidate_recordset(["l10n_ar_sircip_warning"])
            self.assertIn(buenos_aires.name, fiscal_position.l10n_ar_sircip_warning)
        with self.subTest("saving again duplicates nothing"):
            lines_before = self._sircip_lines(self.company_ri)
            self._save_settings(self.company_ri)
            self.assertEqual(self._sircip_lines(self.company_ri), lines_before)
            self.assertEqual(
                self.env["account.journal"].search_count(
                    [("code", "=", "SIRC"), ("company_id", "=", self.company_ri.id)]
                ),
                len(self.settlement_journal),
            )
