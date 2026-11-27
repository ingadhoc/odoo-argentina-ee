from odoo.addons.l10n_ar_account_reports_backward_comp.hooks import EARNINGS_APPLIED_XMLID_NAMES, post_init_hook
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPostInitHook(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {"name": "AR hook company", "chart_template": "ar_ri", "country_id": cls.env.ref("base.ar").id}
        )
        cls.tax_group = cls.env["account.tax.group"].create({"name": "Hook group", "company_id": cls.company.id})

    def _create_tax(self, name, xmlid_name=None):
        tax = self.env["account.tax"].create(
            {
                "name": name,
                "amount_type": "percent",
                "amount": 0.0,
                "type_tax_use": "none",
                "tax_group_id": self.tax_group.id,
                "company_id": self.company.id,
            }
        )
        if xmlid_name:
            self.env["ir.model.data"].create(
                {
                    "module": "l10n_ar_tax",
                    "name": f"{self.company.id}_{xmlid_name}",
                    "model": "account.tax",
                    "res_id": tax.id,
                }
            )
        return tax

    def test_archives_old_earnings_applied_tax(self):
        for xmlid_name in EARNINGS_APPLIED_XMLID_NAMES:
            tax = self._create_tax("Old earnings applied %s" % xmlid_name, xmlid_name)
            self.assertTrue(tax.active)
            self.assertFalse(tax.is_backward_tax)
            post_init_hook(self.env)
            self.assertFalse(tax.active)
            self.assertTrue(tax.is_backward_tax)

    def test_does_not_touch_other_taxes_and_is_idempotent(self):
        other = self._create_tax("Other tax")
        old = self._create_tax("Old earnings applied", EARNINGS_APPLIED_XMLID_NAMES[0])
        post_init_hook(self.env)
        post_init_hook(self.env)
        self.assertTrue(other.active)
        self.assertFalse(other.is_backward_tax)
        self.assertFalse(old.active)
        self.assertTrue(old.is_backward_tax)
