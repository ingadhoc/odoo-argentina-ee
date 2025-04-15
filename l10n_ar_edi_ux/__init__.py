##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from . import models
from . import wizards
from .monkey_patches import monkey_patches

import logging

logger = logging.getLogger(__name__)


def post_init_hook(env):
    ar_companies = env["res.company"].search([]).filtered(lambda x: x.country_id.code == "AR")
    for company in ar_companies:
        logger.info("Set default foreign currency payment policy for AR companies on install")
        key = f"l10n_ar_edi.{company.id}_foreign_currency_payment"
        env["ir.config_parameter"].sudo().set_param(key, "account")
