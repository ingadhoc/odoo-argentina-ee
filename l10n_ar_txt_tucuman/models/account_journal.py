from odoo import models, fields
from odoo.exceptions import ValidationError
import re

def get_pos_and_number(full_number):
    """
    Para un numero nos fijamos si hay '-', si hay:
    * mas de 1, entonces devolvemos error
    * 1, entonces devolvemos las partes (solo parte númerica)
    * 0, entonces devolvemos '0' y parte númerica del número que se pasó
    """
    args = full_number.split('-')
    if len(args) == 1:
        # si no hay '-' tomamos punto de venta 0
        return ('0', re.sub('[^0-9]', '', args[0]))
    else:
        return re.sub('[^0-9]', '', args[0]), re.sub('[^0-9]', '', ''.join(args[1:]))

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

        if nc_without_reversed_entry_id := move_lines.filtered(lambda x: x.move_type == 'out_refund' and not x.move_id.reversed_entry_id):
            raise ValidationError(f"Algunos comprobantes rectificativos no contienen información de que comprobante original están revirtiendo: %s" % (", ".join(nc_without_reversed_entry_id.mapped('move_id.name'))))

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
            # 99 para retenciones por el ejemplo que pasó en el archivo adjunto el cliente en la tarea
            content_datos += line.move_id.l10n_latam_document_type_id.code if line.l10n_latam_document_type_id.internal_type == 'invoice' else '99'
            # LETRA, longitud: 1
            content_datos += line.move_id.l10n_latam_document_type_id.l10n_ar_letter if line.l10n_latam_document_type_id.internal_type == 'invoice' else ' '
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
            content_retper += line.partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code
            # DOCUMENTO, longitud: 11
            content_retper += line.partner_id.ensure_vat()
            # NOMBRE, longitud: 40
            content_retper += line.partner_id.name
            # DOMICILIO, longitud: 40
            content_retper += line.partner_id.street
            # Nro, longitud: 5
            # Hacemos '9' * 5 por el ejemplo que pasó en el archivo adjunto el cliente en la tarea
            content_retper += '9' * 5
            # LOCALIDAD, longitud: 15
            content_retper += line.partner_id.city
            # PROVINCIA, longitud: 15
            content_retper += line.partner_id.city
            # NO USADO, longitud 11
            content_retper += ' ' * 11
            # C. POSTAL, longitud: 8
            content_retper += line.partner_id.zip
            content_retper += '\r\n'

            # Archivo NCFACT.TXT
            # COD. LUGAR EMISION NC, longitud: 4
            if line.move_type == 'out_refund':
                pos_nc, number_nc = get_pos_and_number(line.move_id.l10n_latam_document_number)
                content_ncfact += pos_nc[:4]
                # NUMERO NV, longitud: 8
                content_ncfact += number_nc
                # COD LUGAR EMISION FAC, longitud: 4
                pos, number = get_pos_and_number(line.move_id.reversed_entry_id.l10n_latam_document_number)
                content_ncfact += pospos_nc[:4]
                # NUMERO FAC, longitud: 8
                content_ncfact += number
                # TIPO FAC, longitud: 2
                content_ncfact += '01'
                content_ncfact += '\r\n'

        return [{
            'txt_filename': 'DATOS.txt',
            'txt_content': content_datos,
            },
            {'txt_filename': 'RETPER.txt',
            'txt_content': content_retper,
            },
            {'txt_filename': 'NCFACT.TXT',
            'txt_content': content_ncfact,
            }]
