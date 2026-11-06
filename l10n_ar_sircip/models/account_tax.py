##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models

# DDJJ TXT record type (field 5) declared by each SIRCIP tax. Types 2 (informative), 3 (excluded) and
# 6 (cancelled) have no tax: 2 comes from the period invoices, 6 from credit notes.
SIRCIP_RECORD_PERCEPTION = "1"
SIRCIP_RECORD_NOT_REGISTERED = "4"
SIRCIP_RECORD_SURCHARGE = "5"


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_ar_sircip_record_type = fields.Selection(
        [
            (SIRCIP_RECORD_PERCEPTION, "1 - Percepción"),
            (SIRCIP_RECORD_NOT_REGISTERED, "4 - No inscripto"),
            (SIRCIP_RECORD_SURCHARGE, "5 - Sobretasa"),
        ],
        string="SIRCIP Record Type",
        help="Record type (field 5) with which this tax is reported in the SIRCIP DDJJ file.",
    )
