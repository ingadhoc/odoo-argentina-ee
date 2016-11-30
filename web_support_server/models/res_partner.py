# -*- encoding: utf-8 -*-
from openerp import models, fields
import logging
_logger = logging.getLogger(__name__)


class res_partner(models.Model):
    _inherit = "res.partner"

    support_uuid = fields.Char(
        'Remote Partner UUID',
        readonly=True,
        copy=False,
    )
