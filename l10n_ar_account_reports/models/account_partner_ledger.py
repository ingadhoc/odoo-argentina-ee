# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api
# from openerp.exceptions import ValidationError


class ReportPartnerLedger(models.AbstractModel):
    _inherit = "account.partner.ledger"

    @api.model
    def _lines(self, line_id=None):
        """
        Add document number on partner ledger
        """
        lines = super(ReportPartnerLedger, self)._lines(line_id=line_id)
        for line in lines:
            if line['type'] == 'line':
                partner = self.env['res.partner'].browse(line['id'])
                if partner.main_id_number and partner.main_id_category_id:
                    line['name'] += " (%s: %s)" % (
                        partner.main_id_category_id.code,
                        partner.main_id_number)
        return lines
