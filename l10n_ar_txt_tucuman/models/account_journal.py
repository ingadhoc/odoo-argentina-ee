from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_round
# from odoo.tools.misc import formatLang
# from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import re


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    settlement_tax = fields.Selection(selection_add=[
        ('iibb_tucuman', 'TXT Retenciones/Percepciones Tucuman')
    ])

    def iibb_tucuman_files_values(self, move_lines):
        """ Implementado segun especificación indicada en tarea 38200."""
        self.ensure_one()
        content_datos = ''
        content_retper = ''
        content_ncfact = ''
        # Percepciones
        for line in move_lines.sorted(key=lambda r: (r.date, r.id)):
            # Archivo DATOS.TXT
            # FECHA, longitud: 8. Formato AAAAMMDD
            content_datos += fields.Date.from_string(line.date).strftime('%Y/%m/%d')
            # TIPODOC, longitud: 2
            content_datos += line.partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code
            # DOCUMENTO, longitud: 11
            content_datos += line.partner_id.ensure_vat()
            # TIPO COMP, longitud: 2
            content_datos += line.move_id.l10n_latam_document_type_id.code
            # LETRA, longitud: 1
            content_datos += line.move_id.l10n_latam_document_type_id.l10n_ar_letter
            # COD. LUGAR EMISION, longitud: 4
            content_datos += '0' * 4
            # NUMERO, longitud: 8
            content_datos += '234345'
            # BASE_CALCULO, longitud: 15,2
            content_datos += str(line.tax_base_amount)
            # PORCENTAJE/ALICUOTA, longitud: 6,3
            content_datos += str(line.tax_line_id.get_partner_alicuot(line.partner_id, line.date).alicuota_percepcion)
            # MONTO_RET/PER, longitud: 15,2
            content_datos += str(line.balance)
            content_datos += '\r\n'

            # Archivo RETPER.TXT
            # TIPODOC, longitud: 2
            # DOCUMENTO, longitud: 11
            # NOMBRE, longitud: 40
            # DOMICILIO, longitud: 40
            # Nro, longitud: 5
            # LOCALIDAD, longitud: 15
            # PROVINCIA, longitud: 15
            # NO USADO, longitud 11
            # C. POSTAL, longitud: 8
        return [{
            'txt_filename': 'DATOS.txt',
            'txt_content': content_datos,
            },
            {'txt_filename': 'RETPER.txt',
            'txt_content': content_retper,
            }]
