from odoo import models, fields, _
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    settlement_tax = fields.Selection(selection_add=[
        ('iibb_tucuman', 'TXT Retenciones/Percepciones Tucuman')
    ])

    def iibb_tucuman_files_values(self, move_lines):
        """ Implementado segun especificación indicada en tarea 38200.
        Ver especificación también en l10n_ar_txt_tucuman/doc/MRETPER6R2.pdf a partir de la página 12. """
        self.ensure_one()

        # VALIDACIONES
        self._iibb_tucuman_validations(move_lines)

        # ELABORACIÓN DE ARCHIVOS TXT
        lines = move_lines.sorted(key=lambda r: (r.date, r.id))
        return [{
            'txt_filename': 'DATOS.txt',
            'txt_content': self._iibb_tucuman_datos_txt_file(lines),
            },
            {'txt_filename': 'RETPER.txt',
            'txt_content': self._iibb_tucuman_retper_txt_file(lines),
            },
            {'txt_filename': 'NCFACT.TXT',
            'txt_content': self._iibb_tucuman_ncfact_txt_file(lines.filtered(lambda x: x.move_type == 'out_refund')),
            }]

    def _iibb_tucuman_validations(self, move_lines):
        """ Validaciones para el archivo TXT Retenciones/Percepciones Tucuman. Si no hay errores este método no
        devuelve nada, de lo contrario se lanzará mensaje de error que corresponda indicando lo que el usuario debe
        corregir para poder generar el archivo. """
        if nc_without_reversed_entry_id := move_lines.filtered(lambda x: x.move_type == 'out_refund'
                                                               and not x.move_id.reversed_entry_id):
            raise UserError(_("Algunos comprobantes rectificativos no contienen información de que "
                              "comprobante original están revirtiendo: %s") %
                            (", ".join(nc_without_reversed_entry_id.mapped('move_id.name'))))
        if moves_without_street_city_state := move_lines.filtered(lambda x: not x.partner_id.street or
                                                                  not x.partner_id.city or
                                                                  not x.partner_id.state_id or not x.partner_id.zip):
            raise UserError(_("Algunos comprobantes no contienen información acerca de la calle/ciudad/provincia/cod "
                              "postal del contacto: %s") %
                            (", ".join(moves_without_street_city_state.mapped('move_id.name'))))
        move_lines_with_five_digits_pos = move_lines.filtered(
            lambda x: x.move_id._l10n_ar_get_document_number_parts(
                x.move_id.l10n_latam_document_number,
                x.l10n_latam_document_type_id.code
            )['point_of_sale'] > 9999  # Verificar si el punto de venta es mayor a 9999
        )
        if move_lines_with_five_digits_pos:
            raise UserError(_("Algunos comprobantes tienen punto de venta de 5 dígitos y deben tener de 4 dígitos para "
                              "poder generar el archivo txt de retenciones y percepciones de Tucuman: %s") %
                            (", ".join(move_lines_with_five_digits_pos.mapped('move_id.name'))))
        percepciones = move_lines.filtered(lambda x: x.move_id.is_invoice())
        if percepciones and len(percepciones) != len(move_lines):
            raise UserError(_("Debe generar archivos para TXT Tucuman por separado para retenciones por un lado y "
                              "percepciones por otro."))

    def _iibb_tucuman_datos_txt_file(self, lines):
        """ Devuelve contenido del archivo DATOS.TXT Tucuman. """
        content_datos = ''
        for line in lines:
            is_perception = line.move_id.is_invoice()
            # 1, FECHA, longitud: 8. Formato AAAAMMDD
            content_datos += fields.Date.from_string(line.date).strftime('%Y%m%d')
            # 2, TIPODOC, longitud: 2
            content_datos += line.partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code
            # 3, DOCUMENTO, longitud: 11
            content_datos += line.partner_id.l10n_ar_vat
            # 4, TIPO COMP, longitud: 2
            # 99 para retenciones por el ejemplo que pasó en el archivo adjunto el cliente en la tarea 38200
            content_datos += line.move_id.l10n_latam_document_type_id.code.zfill(2) if is_perception else '99'
            # 5, LETRA, longitud: 1
            content_datos += line.move_id.l10n_latam_document_type_id.l10n_ar_letter if is_perception else ' '
            # 6, COD. LUGAR EMISION, longitud: 4
            document_number_parts = line.move_id._l10n_ar_get_document_number_parts(
                line.move_id.l10n_latam_document_number, line.l10n_latam_document_type_id.code)
            content_datos += str(document_number_parts['point_of_sale']).zfill(4)
            # 7, NUMERO, longitud: 8
            content_datos += str(document_number_parts['invoice_number']).zfill(8)
            # 8, BASE_CALCULO, longitud: 15,2
            content_datos += '%015.2f' % (line.tax_base_amount if is_perception else line.payment_id.withholding_base_amount)
            # 9, PORCENTAJE/ALICUOTA, longitud: 6,3
            partner_alicuot = line.tax_line_id.get_partner_alicuot(line.partner_id, line.date)
            if is_perception:
                content_datos += '%06.3f' % partner_alicuot.alicuota_percepcion
            else:
                content_datos += '%06.3f' % partner_alicuot.alicuota_retencion
            # 10, MONTO_RET/PER, longitud: 15,2
            content_datos += '%015.2f' % abs(line.balance)
            content_datos += '\r\n'
        return content_datos

    def _iibb_tucuman_retper_txt_file(self, lines):
        """ Devuelve contenido del archivo RETPER.TXT Tucuman. """
        content_retper = ''
        for line in lines:
            # 1, TIPODOC, longitud: 2
            content_retper += line.partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code
            # 2, DOCUMENTO, longitud: 11
            content_retper += line.partner_id.l10n_ar_vat
            # 3, NOMBRE, longitud: 40
            content_retper += line.partner_id.name[:40].ljust(40)
            # 4, DOMICILIO, longitud: 40
            content_retper += line.partner_id.street[:40].ljust(40)
            # 5, Nro, longitud: 5
            # Hacemos '9' * 5 por el ejemplo que pasó en el archivo adjunto el cliente en la tarea
            content_retper += '9' * 5
            # 6, LOCALIDAD, longitud: 15
            content_retper += line.partner_id.city[:15].ljust(15)
            # 7, PROVINCIA, longitud: 15
            content_retper += line.partner_id.state_id.name[:15].ljust(15)
            # 8, NO USADO, longitud 11
            content_retper += ' ' * 11
            # 9, C. POSTAL, longitud: 8
            content_retper += '%8s' % line.partner_id.zip
            content_retper += '\r\n'
        return content_retper

    def _iibb_tucuman_ncfact_txt_file(self, lines):
        """ Devuelve contenido del archivo NCFACT.TXT Tucuman. """
        content_ncfact = ''
        for line in lines:
            nc_document_number_parts = line.move_id._l10n_ar_get_document_number_parts(
            line.move_id.l10n_latam_document_number, line.l10n_latam_document_type_id.code)
            # 1, COD. LUGAR EMISION NC, longitud: 4
            content_ncfact += str(nc_document_number_parts['point_of_sale']).zfill(4)
            # 2, NUMERO NV, longitud: 8
            content_ncfact += str(nc_document_number_parts['invoice_number']).zfill(8)
            # 3, COD LUGAR EMISION FAC, longitud: 4
            document_number_parts = line.move_id._l10n_ar_get_document_number_parts(
            line.move_id.reversed_entry_id.l10n_latam_document_number,
            line.move_id.reversed_entry_id.l10n_latam_document_type_id.code)
            content_ncfact += str(document_number_parts['point_of_sale']).zfill(4)
            # 4, NUMERO FAC, longitud: 8
            content_ncfact += str(document_number_parts['invoice_number']).zfill(8)
            # 5, TIPO FAC, longitud: 2
            content_ncfact += line.move_id.reversed_entry_id.l10n_latam_document_type_id.code.zfill(2)
            content_ncfact += '\r\n'
        return content_ncfact
