import os
from types import SimpleNamespace
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from odoo import fields
from odoo.addons.l10n_ar_edi.tests.common import ArMockedClient, TestArEdiCommon

from ..models.account_move import ERRORS_KEY, FLAG_ENV, FLAG_PARAM


class ArcaDown(Exception):
    """ARCA did not answer."""


class FakeArca:
    """What ARCA registered for the journal under test, and how it answers.

    Mimics the behaviour measured in homologation: it evaluates the details in order, registers the approved
    ones and stops at the first rejected one.
    """

    def __init__(self, today):
        self.today = today
        self.registered = {}  # number -> detail sent, plus the CAE ARCA gave it
        self.sends = 0
        self.reset()

    def reset(self):
        self.reject = set()  # totals ARCA rejects: it rejects by content, never by number
        self.lose_after = None  # ARCA registers this many details, then the answer gets lost
        self.down_after_send = False  # and ARCA stays down after losing it
        self.down = False  # every query fails

    def last(self):
        if self.down:
            raise ArcaDown("connection refused")
        return max(self.registered, default=0)

    def _register(self, detail):
        number = detail["CbteDesde"]
        self.registered[number] = dict(detail, CAE=str(70000000000000 + number))
        return self.registered[number]

    def send(self, request):
        self.sends += 1
        details = request["FeDetReq"]["FECAEDetRequest"]
        if self.down:
            raise ArcaDown("connection refused")
        if self.lose_after is not None:
            for detail in details[: self.lose_after]:
                self._register(detail)
            self.down = self.down_after_send
            raise ArcaDown("read timeout")
        if details[0]["CbteDesde"] != self.last() + 1:
            err = SimpleNamespace(Code=10016, Msg="El numero de comprobante no es el proximo a autorizar")
            return SimpleNamespace(Errors=SimpleNamespace(Err=[err]), FeDetResp=None)
        results, stopped = [], False
        for detail in details:
            if stopped or float(detail["ImpTotal"]) in self.reject:
                stopped = True
                results.append(self._result(detail, "R"))
                continue
            results.append(self._result(self._register(detail), "A"))
        return SimpleNamespace(Errors=None, FeDetResp=SimpleNamespace(FECAEDetResponse=results))

    def _result(self, detail, result):
        return SimpleNamespace(
            CbteDesde=detail["CbteDesde"],
            Resultado=result,
            CAE=detail.get("CAE"),
            CAEFchVto=(self.today + relativedelta(days=10)).strftime("%Y%m%d"),
            Observaciones=SimpleNamespace(Obs=[SimpleNamespace(Code=10000, Msg="Rejected in test")])
            if result == "R"
            else None,
        )

    def consult(self, number):
        if self.down:
            raise ArcaDown("connection refused")
        detail = self.registered.get(number)
        if not detail:
            return SimpleNamespace(Errors=SimpleNamespace(Err=[SimpleNamespace(Code=602)]), ResultGet=None)
        return SimpleNamespace(
            Errors=None,
            ResultGet=SimpleNamespace(
                CbteFch=detail["CbteFch"],
                ImpTotal=detail["ImpTotal"],
                DocNro=detail["DocNro"],
                EmisionTipo="CAE",
                CodAutorizacion=detail["CAE"],
                FchVto=(self.today + relativedelta(days=10)).strftime("%Y%m%d"),
                Resultado="A",
            ),
        )


class BatchCaeCommon(TestArEdiCommon):
    """Batch CAE scenarios against a fake ARCA: the connection, the request and the queries never leave Odoo."""

    @classmethod
    @TestArEdiCommon.setup_afip_ws("wsfe")
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()
        cls.partner = cls.res_partner_adhoc
        cls.journal = cls._create_journal("wsfe")
        # With a certificate the company leaves the local dummy validation; the connection itself is faked below.
        cls.company_ri.l10n_ar_afip_ws_crt_id = cls.ar_certificate_1
        cls.env["ir.config_parameter"].sudo().set_param(FLAG_PARAM, "1")
        cls.startClassPatcher(patch.dict(os.environ))
        os.environ.pop(FLAG_ENV, None)

        cls.arca = arca = FakeArca(cls.today)
        client = ArMockedClient()
        client.service = SimpleNamespace(FECompConsultar=lambda auth, query: arca.consult(query["CbteNro"]))
        transport = SimpleNamespace(xml_request="<FECAESolicitar/>", xml_response=None)
        connection = SimpleNamespace(_get_client=lambda return_transport=False: (client, {}, transport))
        Move = cls.registry["account.move"]
        for model, method, fake in [
            (cls.registry["res.company"], "_l10n_ar_get_connection", lambda self, afip_ws: connection),
            (cls.registry["account.journal"], "_l10n_ar_get_afip_last_invoice_number", lambda self, doc: arca.last()),
            (Move, "_ws_verify_request_data", lambda self, client, auth, method, request: None),
            (Move, "_move_batch_send", lambda self, client, auth, request: arca.send(request)),
        ]:
            cls.startClassPatcher(patch.object(model, method, fake))

    def setUp(self):
        super().setUp()
        # Each test starts from the class data, so ARCA starts empty too.
        self.arca.registered.clear()
        self.arca.sends = 0
        self.arca.reset()

    def _create_invoices(self, count):
        return self.env["account.move"].concat(
            *(self._create_invoice_ar(journal_id=self.journal, invoice_date=self.today) for _i in range(count))
        )

    def _post_batch(self, invoices):
        """Post as the background cron does: no commit, and the ARCA rejections collected instead of raised."""
        self.env.cr.cache.pop(ERRORS_KEY, None)
        invoices.with_context(l10n_ar_invoice_skip_commit=True, l10n_ar_batch_collect_errors=True).action_post()
        return self.env.cr.cache.pop(ERRORS_KEY, {})

    def _number(self, invoice):
        return invoice._l10n_ar_get_document_number_parts(
            invoice.l10n_latam_document_number, invoice.l10n_latam_document_type_id.code
        )["invoice_number"]

    def assert_batch_coherence(self):
        """Odoo and ARCA agree on the journal under test: same numbers, same CAE, no gaps."""
        moves = self.env["account.move"].search([("journal_id", "=", self.journal.id)])
        posted = moves.filtered(lambda m: m.state == "posted")
        for move in moves - posted:
            self.assertFalse(move.l10n_ar_afip_auth_code, f"{move.id} is in draft and has a CAE")
        by_number = {self._number(move): move for move in posted}
        self.assertEqual(sorted(by_number), sorted(self.arca.registered), "Odoo and ARCA posted different numbers")
        self.assertEqual(sorted(by_number), list(range(1, len(by_number) + 1)), "The posted numbers have gaps")
        for number, move in by_number.items():
            self.assertEqual(move.l10n_ar_afip_auth_code, self.arca.registered[number]["CAE"], f"Wrong CAE on {number}")
