from itertools import count

from odoo import Command
from odoo.addons.l10n_ar_withholding.tests.test_withholding_ar_ri import TestArWithholdingArRi

# 1st fortnight of a period far from anything the database may already carry,
# so the period constraint is only ever exercised against records of the test
TEST_PERIOD_DATE = "2015-06-10"


class L10nArArbaWsCommon(TestArWithholdingArRi):
    # `name` holds the id ARBA gives the declaration and is globally unique, so the
    # tests mint their own instead of hardcoding one that the database may already hold
    _arba_id_seq = count(900000001)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dj_model = cls.env["l10n_ar.dj.arba"]
        cls.arba_company = cls.company_ri
        # Batch import by default: automatic mode reports to ARBA on payment post,
        # which is a different mechanism than the ones under test here
        cls.arba_company.write({"l10n_ar_arba_env": "demo", "l10n_ar_arba_wh_mode": "batch_import"})

    def _next_arba_id(self):
        return str(next(self._arba_id_seq))

    def _create_ddjj(self, state="draft", date=TEST_PERIOD_DATE, name=None):
        """Create a DDJJ in the given state, bypassing the webservice."""
        ddjj = self.dj_model.create({"company_id": self.arba_company.id, "date": date})
        values = {key: value for key, value in (("name", name), ("state", state)) if value}
        if values:
            ddjj.write(values)
        return ddjj

    def _create_withholding_line(self, ddjj, cert_number):
        """Create a supplier payment carrying a withholding already reported to ARBA."""
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.res_partner_adhoc.id,
                "company_id": self.arba_company.id,
                "journal_id": self.company_data["default_journal_bank"].id,
                "date": TEST_PERIOD_DATE,
                "amount": 1000.0,
                "l10n_ar_withholding_line_ids": [
                    Command.create({"tax_id": self.tax_wth_test_2.id, "base_amount": 1000.0, "amount": 100.0})
                ],
            }
        )
        line = payment.l10n_ar_withholding_line_ids
        line.write({"l10n_ar_dj_arba_id": ddjj.id, "l10n_ar_cert_number": cert_number})
        return line
