##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    settlement_tax = fields.Selection(
        selection_add=[
            ("iibb_aplicado_sircip", "TXT Perc IIBB SIRCIP aplicadas"),
        ]
    )

    def iibb_aplicado_sircip_files_values(self, move_lines):
        """Genera el archivo TXT de presentación de DDJJ para el SIRCIP.

        Especificación oficial de diseño de registros:
        https://www.ca.gob.ar/descargas/sircip/registros/Diseno_de_Registros_del_Sistema_SIRCIP.pdf

        TODO: implementar según el diseño de registros oficial una vez revisado el PDF.
        El patrón de implementación a seguir es iibb_aplicado_sircar_files_values()
        en l10n_ar_account_tax_settlement/models/account_journal.py línea 866.
        """
        raise UserError(
            "La generación del TXT SIRCIP aún no está implementada. "
            "Consultar el diseño de registros oficial en "
            "https://www.ca.gob.ar/descargas/sircip/registros/Diseno_de_Registros_del_Sistema_SIRCIP.pdf"
        )
