from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import L10nArArbaWsCommon

DDJJ_LOGGER = "odoo.addons.l10n_ar_arba_ws.models.l10n_ar_dj_arba"

# ARBA answers business errors inside a 2xx body. Evidence: the chatter of ticket
# 123858 renders them as a dict, which is only reached when the response had no error.
NOT_FOUND = {"status": 404, "error": "DDJJ_NO_ENCONTRADA", "message": "Declaración Jurada no encontrada"}
IN_PROGRESS = {"status": 400, "error": "ERROR_DDJJ_EN_GESTION", "message": "La DDJJ esta en un estado invalido"}
OPEN_IN_ARBA = {"id": 138514, "estado": "Abierto"}
# Shape of the same error should ARBA ever report it with a non 2xx status
NOT_FOUND_AS_ERROR = "404 - DDJJ_NO_ENCONTRADA Declaración Jurada no encontrada"


@tagged("-at_install", "post_install")
class TestUpdateStatus(L10nArArbaWsCommon):
    """Task 71519: only DDJJ_NO_ENCONTRADA cancels the DDJJ.

    That answer means the declaration was deleted from the ARBA portal. Any other
    error leaves it open so it keeps being retried.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The demo environment short-circuits action_update_status before it asks ARBA
        cls.arba_company.l10n_ar_arba_env = "testing"

    @mute_logger(DDJJ_LOGGER)
    def test_update_status_routes_arba_answers(self):
        ddjj = self._create_ddjj(state="open", name=self._next_arba_id())

        with self.subTest("the declaration is open in ARBA, the DDJJ stays open"):
            self._update_status(ddjj, response=OPEN_IN_ARBA)
            self.assertEqual(ddjj.state, "open")

        with self.subTest("an error other than DDJJ_NO_ENCONTRADA does not cancel the DDJJ"):
            self._update_status(ddjj, response=IN_PROGRESS)
            self.assertEqual(ddjj.state, "open")

        with self.subTest("DDJJ_NO_ENCONTRADA in the payload cancels the DDJJ"):
            self._update_status(ddjj, response=NOT_FOUND)
            self.assertEqual(ddjj.state, "cancel")

    @mute_logger(DDJJ_LOGGER)
    def test_update_status_cancels_on_a_non_2xx_not_found(self):
        """The same error reported as an HTTP status must cancel the DDJJ too."""
        ddjj = self._create_ddjj(state="open", date="2015-06-20", name=self._next_arba_id())

        self._update_status(ddjj, error=NOT_FOUND_AS_ERROR)

        self.assertEqual(ddjj.state, "cancel")

    def _update_status(self, ddjj, response=None, error=False):
        """Run action_update_status against a canned answer from ARBA."""
        with patch.object(type(ddjj), "_process_arba_response", return_value=(response, error)):
            ddjj.action_update_status()
