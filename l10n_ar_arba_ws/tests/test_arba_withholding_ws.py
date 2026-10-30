import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import requests
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.tests import tagged
from odoo.tools import mute_logger

WS_LOGGER = "odoo.addons.l10n_ar_arba_ws.models.l10n_ar_dj_arba"

DUPLICATED_ANSWER = (
    400,
    {
        "status": 400,
        "error": "ERROR_DUPLICIDAD_NUMERO_TRANSACCION",
        "message": "Número de transacción ya existente para esta actividad y período",
    },
)


@tagged("post_install_l10n", "post_install", "-at_install")
class TestArbaWithholdingWs(TestArCommon):
    """Informar una retención a ARBA sin salir a ARBA: los requests se simulan con respuestas armadas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_ri.l10n_ar_arba_env = "testing"
        arba_tax = cls.env.ref("account.%i_ex_tax_withholding_iibb_ba_applied" % cls.company_ri.id)
        cls.ddjj = cls.env["l10n_ar.dj.arba"].create(
            {"company_id": cls.company_ri.id, "date": "2026-10-23", "name": "35684", "state": "open"}
        )
        payment = cls.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": cls.res_partner_adhoc.id,
                "journal_id": cls.company_data["default_journal_bank"].id,
                "amount": 251502.07,
                "date": "2026-10-23",
            }
        )
        # compute the automatic withholdings first, otherwise they would replace the line created below
        payment.flush_recordset()
        cls.wh_line = cls.env["l10n_ar.payment.withholding"].create(
            {
                "payment_id": payment.id,
                "tax_id": arba_tax.id,
                "name": "00001313",
                "base_amount": 253275.0,
                "amount": 1772.93,
            }
        )

    @contextmanager
    def _arba_answers(self, *answers):
        """Each answer is an exception to raise or a (status_code, body) pair, consumed in call order."""
        answers = list(answers)
        calls = []

        def _fake_request(method, url, **kwargs):
            calls.append((method, url))
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            status_code, body = answer
            response = requests.Response()
            response.status_code = status_code
            response._content = json.dumps(body).encode()
            return response

        connection = SimpleNamespace(token="test-token", _l10n_ar_get_afip_ws_url=lambda ws, env: "https://arba.test")

        def _fake_connection(company, ws):
            # a commit in the middle of the payment posting would break its savepoints
            self.assertTrue(company.env.context.get("l10n_ar_invoice_skip_commit"))
            return connection

        with (
            patch.object(type(self.env["res.company"]), "_l10n_ar_get_connection", _fake_connection),
            patch.object(requests, "request", _fake_request),
        ):
            yield calls
        self.assertFalse(answers, "ARBA was called fewer times than expected")

    def _arba_withholding(self, **values):
        return {
            "nroTransaccionAgente": "1313",
            "importeRetenido": 1772.93,
            "nroEmision": "2026/00001/00000299",
            **values,
        }

    def test_new_withholding_gets_certificate(self):
        with self._arba_answers((200, {"nroEmision": "2026/00001/00000300"})):
            self.ddjj._create_withholding(self.wh_line)

        self.assertEqual(self.wh_line.l10n_ar_cert_number, "2026/00001/00000300")
        self.assertEqual(self.wh_line.name, "2026/00001/00000300")
        self.assertEqual(self.wh_line.ref, "00001313")
        self.assertEqual(self.wh_line.l10n_ar_dj_arba_id, self.ddjj)

    @mute_logger(WS_LOGGER)
    def test_connection_reset_then_duplicated_links_existing_withholding(self):
        """The first POST reaches ARBA but its answer is lost: the retry is rejected as duplicated
        and the certificate is taken from the withholding ARBA already has."""
        with self._arba_answers(
            requests.exceptions.ConnectionError("Connection aborted."),
            DUPLICATED_ANSWER,
            (200, [self._arba_withholding(nroTransaccionAgente="999"), self._arba_withholding()]),
        ) as calls:
            self.ddjj._create_withholding(self.wh_line)

        self.assertEqual([method for method, _url in calls], ["POST", "POST", "GET"])
        self.assertIn("idDj=35684", calls[2][1])
        self.assertEqual(self.wh_line.l10n_ar_cert_number, "2026/00001/00000299")
        self.assertEqual(self.wh_line.name, "2026/00001/00000299")
        self.assertEqual(self.wh_line.ref, "00001313")
        self.assertEqual(self.wh_line.l10n_ar_dj_arba_id, self.ddjj)

    @mute_logger(WS_LOGGER)
    def test_duplicated_accepts_single_object_answer(self):
        with self._arba_answers(DUPLICATED_ANSWER, (200, self._arba_withholding())):
            self.ddjj._create_withholding(self.wh_line)

        self.assertEqual(self.wh_line.l10n_ar_cert_number, "2026/00001/00000299")

    @mute_logger(WS_LOGGER)
    def test_duplicated_without_matching_withholding_keeps_error(self):
        """Another amount or a cancelled withholding is not ours: nothing is linked and the error stays."""
        with self._arba_answers(
            DUPLICATED_ANSWER,
            (
                200,
                [
                    self._arba_withholding(importeRetenido=1000.0),
                    self._arba_withholding(fechaBaja="2026-10-23T12:00:00"),
                ],
            ),
        ):
            self.ddjj._create_withholding(self.wh_line)

        self.assertFalse(self.wh_line.l10n_ar_cert_number)
        self.assertEqual(self.wh_line.name, "00001313")
        self.assertIn("ERROR_DUPLICIDAD_NUMERO_TRANSACCION", self.wh_line.payment_id.message_ids[0].body)
