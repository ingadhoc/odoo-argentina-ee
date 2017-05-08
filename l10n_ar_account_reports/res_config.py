# -*- coding: utf-8 -*-
from openerp import models, fields
import logging
_logger = logging.getLogger(__name__)


class AccountConfigSsettings(models.TransientModel):
    _inherit = 'account.config.settings'

    group_beta_argentina_reports = fields.Boolean(
        'Activar reportes argentinos BETA',
        help='Tenga en cuenta que los reportes en estado BETA todavía no han '
        'sido depurados ni testeados en profundiad. Los mismos pueden contener'
        ' errores y puden surgir cambios. Cualquier feedback a ADHOC '
        ' es bienvenido',
        implied_group='l10n_ar_account_reports.group_beta_argentina_reports',
    )
