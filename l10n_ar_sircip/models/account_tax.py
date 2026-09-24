##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models

# Tipo de Registro del TXT de DDJJ (campo 5) que declara cada impuesto SIRCIP.
# Los tipos 2 (informativo), 3 (excluido) y 6 (anulada) no tienen impuesto propio:
# el 2 sale de cruzar las facturas del período, el 6 de las notas de crédito.
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
