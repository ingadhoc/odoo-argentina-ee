# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.l10n_ar_edi.tests.common import TestEdi
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)


@tagged('external_l10n', '-at_install', 'post_install', '-standard', 'external')
class TestCAEA(TestEdi):

    @classmethod
    def setUpClass(cls):
        pass
        # Create WSFE, CAEA regular and CAEA cotigency journals
        # Configure contigency joournal to the regular journal

    def test_01(self):
        pass
        # Create CAEA manually an by cron

        # Send CAEA invoices, manually and by cron

        # Inform CAEA without invoices, manually and by cron

        # Activate Cotigency and review if the invoice automatically change
        # to contigency journal

        # Report invoices to CAEA of different joruanls and the same time
