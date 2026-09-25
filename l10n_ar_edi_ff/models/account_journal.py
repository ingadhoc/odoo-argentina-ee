from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ar_batch_cae = fields.Boolean(
        string="Request CAE in batches",
        help="Customer invoices of this journal are sent to ARCA in batches (one request for several invoices) "
        "instead of one request per invoice. Only for the Electronic Invoice web service (wsfe).",
    )

    @api.constrains("l10n_ar_batch_cae", "l10n_ar_afip_pos_system")
    def _check_l10n_ar_batch_cae(self):
        for journal in self.filtered("l10n_ar_batch_cae"):
            if journal.l10n_ar_afip_ws != "wsfe":
                raise ValidationError(
                    self.env._("Batch CAE requests are only available for the Electronic Invoice web service (wsfe).")
                )
