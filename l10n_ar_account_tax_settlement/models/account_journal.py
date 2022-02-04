from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
# from odoo.tools.misc import formatLang
# from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import re

#########
# helpers
#########


def format_amount(amount, padding=15, decimals=2, sep=""):
    if amount < 0:
        template = "-{:0>%dd}" % (padding - 1 - len(sep))
    else:
        template = "{:0>%dd}" % (padding - len(sep))
    res = template.format(
        int(round(abs(amount) * 10**decimals, decimals)))
    if sep:
        res = "{0}{1}{2}".format(res[:-decimals], sep, res[-decimals:])
    return res


def get_line_tax_base(move_line):
    return sum(move_line.move_id.line_ids.filtered(
        lambda x: move_line.tax_line_id in x.tax_ids).mapped(
        'balance'))


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

    # TODO ver como queremos separar la de santa fe, arba y demás. usamos uno
    # solo y luego logica adentro? un diario para cada una?
    settlement_tax = fields.Selection(selection_add=[
        # ('vat', 'VAT'),
        # ('profits', 'Profits'),
        ('sicore_aplicado', 'TXT SICORE Aplicado'),
        ('iibb_sufrido', 'TXT IIBB p/ SIFERE'),
        ('iibb_aplicado', 'TXT Perc/Ret IIBB aplicadas ARBA: Percepciones ( excepto actividad 29, 7 quincenal, 7 y 17 de Bancos)'),
        ('iibb_aplicado_act_7', 'TXT Perc/Ret IIBB aplicadas ARBA: Percepciones Act. 7 método Percibido (quincenal)'),
        ('iibb_aplicado_agip', 'TXT Perc/Ret IIBB aplicadas AGIP'),
        ('iibb_aplicado_api', 'TXT Perc/Ret IIBB aplicadas API'),
        ('iibb_aplicado_sircar', 'TXT Perc/Ret IIBB aplicadas SIRCAR'),
        ('iibb_aplicado_dgr_mendoza', 'TXT  Perc/Ret IIBB aplicado DGR Mendonza'),
        # ('other', 'Other')
    ])

    # def action_create_tax_settlement_entry(self):
    #     if self.settlement_tax == 'profits':
    #         self = self.with_context(quincenal=True)
    #     return super(
    #         AccountJournal, self).action_create_tax_settlement_entry()

    @api.constrains('settlement_tax')
    def check_withholding_autmatic_installed(self):
        account_withholding_automatic = self.env['ir.module.module'].search([
            ('name', '=', 'account_withholding_automatic'),
            ('state', '=', 'installed'),
        ])
        if not account_withholding_automatic and any(self.filtered(
                lambda x: x.settlement_tax in ['iibb_aplicado_api',
                                               'sicore_aplicado'])):
            raise ValidationError(_(
                'No puede utilizar exportación a "SICORE Aplicado"'
                ' o "Perc/Ret IIBB aplicadas API"'
                ' si no tiene instalado el módulo de retenciones'
                ' automáticas (account_withholding_automatic)'))

    def iibb_aplicado_dgr_mendoza_files_values(self, move_lines):

        self.ensure_one()
        ret = ''
        for line in move_lines:
            # Agente de Retención del Impuesto sobre los Ingresos Brutos

            partner = line.partner_id
            payment = line.payment_id
            move = line.move_id
            tax = line.tax_line_id

            alicuot_line = tax.get_partner_alicuot(partner, line.date)
            if not alicuot_line:
                raise ValidationError(_('No hay alicuota configurada en el partner "%s" (id: %s)') % (
                    partner.name, partner.id))

            if not payment:
                continue

            # Campo 1: CUIT char(13). CUIT del Sujeto retenido o percibido. Ejemplo: 20-10111222-3
            # Example "30-58710878-6"
            partner.ensure_vat()
            content = partner.l10n_ar_formatted_vat

            # Campo 2: Denominación char(80). Apellido y Nombre o Razón Social. Formato: 80 posiciones, se completa con
            # blancos a la derecha.
            # Example "ELECTRICIDAD MAZA SRL                                                           "
            content += '{:80.80}'.format(partner.name)

            # Campo 3: Fecha Comprobante char(8). Fecha del Comprobante de Retención/Percepción según Res.40/2012 (ddmmaaaa)
            # Example s"16052020"
            content += fields.Date.from_string(move.date).strftime('%d%m%Y')

            # Campo 4: Comprobante char(12)- Número de Comprobante de Retención/Percepción según Res.40/2012.
            # Formato: 999999999999 (rellenar con ceros (0) a la izquierda) Ejemplo: 000000001521
            # Example "000000027860"
            content += (payment.withholding_number or '').rjust(12, '0')[:12]  # we are forcing 12 first numbers always.

            # Campo 5: Fecha Ret./Perc. char(8)- Fecha de efectuada la retención / percepción (ddmmaaaa)
            # Example "16052020"
            content += fields.Date.from_string(payment.date).strftime('%d%m%Y')

            # Campo 6. Base Imponible char(15). Formato: 999999999999.99 (doce enteros, punto decimal y dos decimales,
            # dejando espacios en blanco a izquierda para completar las 15 posiciones). Ejemplo: "         345.21"
            # Example "000000027229.33"
            content += '%15.2f' % payment.withholdable_base_amount

            # Campo 7: Alícuota char(5). Alícuota para la retención y/o percepción. Formato: 99.99 (dos enteros,
            # punto decimal y dos decimales. Ejemplo: " 3.00"
            # Example "03.00"
            content += '%5.2f' % alicuot_line.alicuota_retencion

            # Campo 8: Importe Ret./Perc. char(15). Importe retenido y/o percibido. Formato: 999999999999.99 (doce enteros,
            # punto decimal y dos decimales, dejando espacios en blanco a izquierda para completar las 15 posiciones).
            # Ejemplo: "          34.50" "000000000816.88"
            content += '%15.2f' % -line.balance

            content += '\r\n'
            ret += content

        # File name
        move_line = move_lines and move_lines[0] or self.env['account.move.line']
        tipo_agente = 'rr'  # This value is fixed just because we are doing the retention txt, when adding the
        # perception we need to change it
        cuit = move_line.company_id.vat
        periodo = fields.Date.from_string(move_line.date).strftime('%Y') or ""  # 'pppp' AÑO '2020'
        cuota = fields.Date.from_string(move_line.date).strftime('%m') or ""  # 'cc'

        return [{
            'txt_filename': '%s%s%s%s.txt' % (tipo_agente, cuit, periodo, cuota),
            'txt_content': ret,
        }]

    def _get_perception_original_invoice_number(self, line):
        self.ensure_one()
        res = ''
        related_invoice = line.move_id._found_related_invoice() or line.move_id
        letter = related_invoice.l10n_latam_document_type_id.l10n_ar_letter
        internal_type = related_invoice.l10n_latam_document_type_id.internal_type

        # 2 Tipo de comprobante
        if internal_type == 'invoice':
            document_type = letter == 'E' and 5 or 1
        elif internal_type == 'credit_note':
            document_type = letter == 'E' and 106 or 102
        elif internal_type == 'debit_note':
            document_type = letter == 'E' and 6 or 2
        elif related_invoice.move_type == 'out_invoice':
            document_type = 20
        elif related_invoice.move_type == 'out_refund':
            document_type = 120
        else:
            raise ValidationError(_('Tipo de comprobante no reconocido'))
        res += str(document_type)[:1]

        # 3 Letra del comprobante
        res += letter

        # 4 Número del comprobante
        res += '%012d' % int(re.sub('[^0-9]', '', related_invoice.l10n_latam_document_number or ''))
        return res

    def iibb_aplicado_api_files_values(self, move_lines):
        """ Implementado segun especificación en carpeta doc de este repo
        """
        def format_amount(amount, integers, decimals=2):
            # overwrite default format_amount
            template = "%0" + "%ss" % (integers + decimals + 1)
            # TODO se podria mejorar haciendo algo asi pero hace falta
            # hacer parametro el 16
            # "{0:>16.2f}".format(12.1)
            return template % "{0:.2f}".format(
                round(amount, decimals)).replace('.', ',')
        self.ensure_one()
        ret = ''
        perc = ''

        for line in move_lines:
            partner = line.partner_id

            tax = line.tax_line_id

            alicuot_line = tax.get_partner_alicuot(partner, line.date)
            if not alicuot_line:
                raise ValidationError(_(
                    'No hay alicuota configurada en el partner '
                    '"%s" (id: %s)') % (partner.name, partner.id))

            # 1 - tipo de operacion
            if tax.type_tax_use in ['sale', 'purchase'] and \
                    tax.amount_type == 'partner_tax':
                content = '2'
                alicuot = alicuot_line.alicuota_percepcion

                # para percepciones ho es obligatorio
                articulo_inciso_calculo = \
                    alicuot_line.api_articulo_inciso_calculo_percepcion \
                    or '000'
                articulo_inciso_retiene = \
                    alicuot_line.api_codigo_articulo_percepcion
            elif tax.type_tax_use in ['customer', 'supplier'] and \
                    tax.withholding_type == 'partner_tax':
                content = '1'
                alicuot = alicuot_line.alicuota_retencion

                articulo_inciso_calculo = \
                    alicuot_line.api_articulo_inciso_calculo_retencion
                articulo_inciso_retiene = \
                    alicuot_line.api_codigo_articulo_retencion
            else:
                raise ValidationError(_(
                    'Tipo de impuesto %s equivocado. Se aceptan solo '
                    'percepciones o retenciones con "Cálculo de impuestos" '
                    'igual a "Alícuota en el Partner". Id de impuestos '
                    '"%s"') % (tax.tax_group_id.name, tax.id))

            if not articulo_inciso_calculo or not articulo_inciso_retiene:
                raise ValidationError(_(
                    'Debe setear la información de "artículo/inciso" en las'
                    ' alícutoas de contacto %s') % partner.name)

            # 2 - fecha
            content += fields.Date.from_string(line.date).strftime('%d/%m/%Y')

            # 3 - Código de artículo Inciso por el que retiene
            content += articulo_inciso_retiene

            # 4 - tipo de comprobante y
            # 5 - letra de comprobante
            internal_type = line.l10n_latam_document_type_id.internal_type
            move = line.move_id

            if internal_type in ('invoice', 'credit_note'):
                # factura
                content += '01' + line.l10n_latam_document_type_id.l10n_ar_letter

            elif internal_type == 'debit_note':
                # ND
                content += '02' + line.l10n_latam_document_type_id.l10n_ar_letter
            else:
                # orden de pago (sin letra)
                # 09 sería otro comprobante y 10 reinitegro de perc/ret
                content += '03 '

            # 6 - numero comprobante Texto(16)
            if internal_type in ('invoice', 'credit_note', 'debit_note'):
                # TODO el aplicativo deberia empezar a aceptar 5 digitos
                pos, number = get_pos_and_number(move.l10n_latam_document_number)
                content += '{:>04s}'.format(pos)
                content += '{:>08s}'.format(number)
                content += '    '
            else:
                content += '%016s' % (move.l10n_latam_document_number or '')

            # 7 - fecha comprobante
            content += fields.Date.from_string(move.date).strftime('%d/%m/%Y')

            # 8 - monto comprobante
            content += format_amount(-line.balance, 11, 2)

            # 9 - tipo de documento
            # nosotros solo permitimos CUIT por ahora
            content += '3'

            # 10 - numero de documento
            content += partner.ensure_vat()

            # 11 - Condición frente a Ingresos Brutos
            # 1 es inscripto, 2 no inscripto con oblig. a insc y 3 no insc sin
            # oblig a insc. TODO implementar 2
            gross_income_type = partner.l10n_ar_gross_income_type
            if not gross_income_type:
                raise ValidationError(_(
                    'Debe setear el tipo de inscripción de IIBB del partner '
                    '"%s" (id: %s)') % (
                    partner.name, partner.id))
            if gross_income_type in ['multilateral', 'local']:
                content += '1'
            else:
                content += '3'

            # 12 - Número de Inscripción en Ingresos Brutos
            content += (re.sub(
                '[^0-9]', '',
                partner.l10n_ar_gross_income_number or '')).rjust(10, '0')

            # 13 - Situación frente a IVA donde:
            # ri (1), rni (2), exento (3), monotr (4)
            res_iva = partner.l10n_ar_afip_responsibility_type_id
            if res_iva.code in ['1', '1FM']:
                # RI
                content += '1'
            elif res_iva.code == '2':
                # RNI
                content += '2'
            elif res_iva.code == '4':
                # EXENTO
                content += '3'
            elif res_iva.code == '6':
                # MONOT
                content += '4'
            else:
                raise ValidationError(_(
                    'La responsabilidad frente a IVA "%s" no está soportada '
                    'para ret/perc Santa Fe') % res_iva.name)

            # 14 - Marca inscripción Otros Gravámenes
            # TODO implementar (requiere nuevo campo en odoo?)
            content += '0'

            # 15 - Marca Inscripción DREI
            # TODO revisar si implementamos o no, aparentemente este campo
            # activo en drei no se usa o no es lo que esperamos, por ahora
            # no lo hacemos requerido para no andar molestando al dope
            # if not partner.drei:
            #     raise ValidationError(_(
            #         'Debe seleccionar situación DREI para partner '
            #         '"%s" (id: %s)') % (
            #             partner.name, partner.id))
            content += partner.drei == 'activo' and '1' or '0'

            # 16 - Importe Otros Gravámenes
            # TODO implementar
            content += format_amount(0.0, 9, 2)

            # 17 - Importe IVA (solo si factura)
            if line.move_id.is_invoice():
                amounts = line.move_id._l10n_ar_get_amounts(company_currency=True)
                vat_amount = amounts['vat_amount']
                base_amount = amounts['vat_untaxed_base_amount']
            else:
                vat_amount = 0.0
                base_amount = line.payment_id and line.payment_id.withholdable_base_amount or 0.0
            content += format_amount(vat_amount, 9, 2)

            # 18 - Base Imponible para el cálculo
            # tal vez la base deberiamos calcularlo asi, en pagos no porque
            # los asientos estan separados
            # content += format_amount(-get_line_tax_base(line), 12, 2, ',')
            content += format_amount(base_amount, 11, 2)

            # 19 - Alícuota / alicuota
            content += format_amount(alicuot, 2, 2)

            # 20 - Impuesto Determinado
            content += format_amount(-line.balance, 11, 2)

            # 21 - Derecho Registro e Inspección
            # TODO implementar
            # es un importe seguramente importe retenido de drei
            content += format_amount(0.0, 9, 2)

            # 22 - Monto Retenido
            # TODO por ahora es igual a impuesto determinado pero, podria ser
            # distinto en algún caso?
            content += format_amount(-line.balance, 11, 2)

            # 23 - Artículo/Inciso para el cálculo
            content += articulo_inciso_calculo

            # 24 - Tipo de Exención
            # TODO implementar. Por ahora no implementamos excenciones ya que
            # a priori no las informan
            content += '0'

            # 25 - Año de Exención
            # TODO implementar
            content += '0000'

            # 26 - Número de Certificado de Exención
            # TODO implementar
            content += '      '

            # 27 - Número de Certificado Propio
            # TODO implementar
            content += '            '

            # new line
            content += '\r\n'

            if tax.type_tax_use in ['sale', 'purchase']:
                perc += content
            elif tax.type_tax_use in ['customer', 'supplier']:
                ret += content

        # return [
        #     {
        #         'txt_filename': 'Perc IIBB API Aplicadas.txt',
        #         'txt_content': perc,
        #     },
        #     {
        #         'txt_filename': 'Ret IIBB API Aplicadas.txt',
        #         'txt_content': ret,
        #     }
        return [
            {
                'txt_filename': 'Perc/Ret IIBB API Aplicadas.txt',
                'txt_content': perc + ret,
            }]

    def iibb_aplicado_agip_files_values(self, move_lines):
        """ Ver readme del modulo para descripcion del formato. Tambien
        archivos de ejemplo en /doc
        """
        self.ensure_one()

        if self.company_id.agip_padron_type != 'regimenes_generales':
            raise ValidationError(_(
                'Por ahora solo esta implementado el padrón de Regímenes '
                'Generales, revise la configuración en "Contabilidad / "'
                'Configuración / Ajustes"'))

        ret_perc = ''
        credito = ''

        company_currency = self.company_id.currency_id
        for line in move_lines.sorted('date'):

            # pay_group = payment.payment_group_id
            move = line.move_id
            payment = line.payment_id
            tax = line.tax_line_id
            partner = line.partner_id
            internal_type = line.l10n_latam_document_type_id.internal_type

            if not partner.vat:
                raise ValidationError(_(
                    'El partner "%s" (id %s) no tiene número de identificación '
                    'seteada') % (partner.name, partner.id))

            alicuot_line = tax.get_partner_alicuot(partner, line.date)
            if not alicuot_line:
                raise ValidationError(_(
                    'No hay alicuota configurada en el partner '
                    '"%s" (id: %s)') % (partner.name, partner.id))


            # 1 - Tipo de Operación
            if tax.type_tax_use in ['sale', 'purchase']:
                    # tax.amount_type == 'partner_tax':
                content = '2'
                alicuot = alicuot_line.alicuota_percepcion
            elif tax.type_tax_use in ['customer', 'supplier']:
                    # tax.withholding_type == 'partner_tax':
                content = '1'
                alicuot = alicuot_line.alicuota_retencion

            # notas de credito
            if internal_type == 'credit_note':
                # 2 - Nro. Nota de crédito
                content += '%012d' % int(
                    re.sub('[^0-9]', '', move.l10n_latam_document_number or ''))

                # 3 - Fecha Nota de crédito
                content += fields.Date.from_string(
                    line.date).strftime('%d/%m/%Y')

                # 4 - Monto nota de crédito
                # TODO implementar devoluciones de pagos
                # content += format_amount(
                #     line.move_id.cc_amount_total, 16, 2, ',')
                # la especificacion no lo dice claro pero un errror al importar
                # si, lo que se espera es el importe base, ya que dice que
                # este, multiplicado por la alícuota, debe ser igual al importe
                # a retener/percibir
                taxable_amount = line.tax_base_amount
                content += format_amount(taxable_amount, 16, 2, ',')

                # 5 - Nro. certificado propio
                # opcional y el que nos pasaron no tenia
                content += '                '

                # segun interpretamos de los daots que nos pasaron 6, 7, 8 y 11
                # son del comprobante original
                or_inv = line.move_id._found_related_invoice()
                if not or_inv:
                    raise ValidationError(_(
                        'No pudimos encontrar el comprobante original para %s '
                        '(id %s). Verifique que en la nota de crédito "%s", el'
                        ' campo origen es el número de la factura original'
                    ) % (
                        line.move_id.display_name,
                        line.move_id.id,
                        line.move_id.display_name))

                # 6 - Tipo de comprobante origen de la retención
                # por ahora solo tenemos facturas implementadas
                content += '01'

                # 7 - Letra del Comprobante
                if payment:
                    content += ' '
                else:
                    content += or_inv.l10n_latam_document_type_id.l10n_ar_letter

                # 8 - Nro de comprobante (original)
                content += '%016d' % int(
                    re.sub('[^0-9]', '', or_inv.l10n_latam_document_number or ''))

                # 9 - Nro de documento del Retenido
                content += partner.vat

                # 10 - Código de norma
                # por ahora solo padron regimenes generales
                content += '029'

                # 11 - Fecha de retención/percepción
                content += fields.Date.from_string(
                    or_inv.invoice_date).strftime('%d/%m/%Y')

                # 12 - Ret/percep a deducir
                content += format_amount(line.balance, 16, 2, ',')

                # 13 - Alícuota
                content += format_amount(alicuot, 5, 2, ',')

                content += '\r\n'

                credito += content
                continue

            # 2 - Código de Norma
            # por ahora solo padron regimenes generales
            content += '029'

            # 3 - Fecha de retención/percepción
            content += fields.Date.from_string(line.date).strftime('%d/%m/%Y')

            # 4 - Tipo de comprobante origen de la retención
            if internal_type == 'invoice':
                content += '01'
            elif internal_type == 'debit_note':
                content += '02'
            else:
                # orden de pago
                content += '03'

            # 5 - Letra del Comprobante
            # segun vemos en los archivos de ejemplo solo en percepciones
            if payment:
                content += ' '
            else:
                content += line.l10n_latam_document_type_id.l10n_ar_letter

            # 6 - Nro de comprobante
            content += '%016d' % int(
                re.sub('[^0-9]', '', move.l10n_latam_document_number or ''))

            # 7 - Fecha del comprobante
            content += fields.Date.from_string(move.date).strftime('%d/%m/%Y')

            # obtenemos montos de los comprobantes
            payment_group = line.payment_id.payment_group_id
            if payment_group:
                # solo en comprobantes A, M segun especificacion
                vat_amount = 0.0
                total_amount = payment_group.payments_amount
                # es lo mismo que payment_group.matched_amount_untaxed
                taxable_amount = payment.withholdable_base_amount

                # lo sacamos por diferencia
                other_taxes_amount = company_currency.round(
                    total_amount - taxable_amount - vat_amount)
            elif line.move_id.is_invoice():
                amounts = line.move_id._l10n_ar_get_amounts(company_currency=True)
                # segun especificacion el iva solo se reporta para estos
                if line.l10n_latam_document_type_id.l10n_ar_letter in ['A', 'M']:
                    vat_amount = amounts['vat_amount']
                else:
                    vat_amount = 0.0

                total_amount = (1 if line.move_id.is_inbound() else -1) * line.move_id.amount_total_signed

                # por si se olvidaron de poner agip en una linea de factura
                # la base la sacamos desde las lineas de impuesto
                # taxable_amount = line.move_id.cc_amount_untaxed
                taxable_amount = line.tax_base_amount

                # tambien lo sacamos por diferencia para no tener error (por el
                # calculo trucado de taxable_amount por ejemplo) y
                # ademas porque el iva solo se reporta si es factura A, M
                other_taxes_amount = company_currency.round(
                    total_amount - taxable_amount - vat_amount)
                # other_taxes_amount = line.move_id.cc_other_taxes_amount
            else:
                raise ValidationError(_('El impuesto no está asociado'))

            # 8 - Monto del comprobante
            content += format_amount(total_amount, 16, 2, ',')

            # 9 - Nro de certificado propio
            content += (payment.withholding_number or '').rjust(16, ' ')

            # 10 - Tipo de documento del Retenido
            # vat
            if partner.l10n_latam_identification_type_id.name not in ['CUIT', 'CUIL', 'CDI']:
                raise ValidationError(_(
                    'EL el partner "%s" (id %s), el tipo de identificación '
                    'debe ser una de siguientes: CUIT, CUIL, CDI.' % (partner.id, partner.name)))
            doc_type_mapping = {'CUIT': '3', 'CUIL': '2', 'CDI': '1'}
            content += doc_type_mapping[partner.l10n_latam_identification_type_id.name]

            # 11 - Nro de documento del Retenido
            content += partner.vat

            # 12 - Situación IB del Retenido
            # 1: Local 2: Convenio Multilateral
            # 4: No inscripto 5: Reg.Simplificado
            if not partner.l10n_ar_gross_income_type:
                raise ValidationError(_(
                    'Debe setear el tipo de inscripción de IIBB del partner '
                    '"%s" (id: %s)') % (partner.name, partner.id))

            # ahora se reportaria para cualquier inscripto el numero de cuit
            gross_income_mapping = {
                'local': '5', 'multilateral': '2', 'exempt': '4'}
            content += gross_income_mapping[partner.l10n_ar_gross_income_type]

            # 13 - Nro Inscripción IB del Retenido
            if partner.l10n_ar_gross_income_type == 'exempt':
                content += '00000000000'
            else:
                content += partner.ensure_vat()

            # 14 - Situación frente al IVA del Retenido
            # 1 - Responsable Inscripto
            # 3 - Exento
            # 4 - Monotributo
            res_iva = partner.l10n_ar_afip_responsibility_type_id
            if res_iva.code in ['1', '1FM']:
                # RI
                content += '1'
            elif res_iva.code == '4':
                # EXENTO
                content += '3'
            elif res_iva.code == '6':
                # MONOT
                content += '4'
            else:
                raise ValidationError(_(
                    'La responsabilidad frente a IVA "%s" no está soportada '
                    'para ret/perc AGIP') % res_iva.name)

            # 15 - Razón Social del Retenido
            content += '{:30.30}'.format(partner.name)

            # 16 - Importe otros conceptos
            content += format_amount(other_taxes_amount, 16, 2, ',')

            # 17 - Importe IVA
            content += format_amount(vat_amount, 16, 2, ',')

            # 18 - Monto Sujeto a Retención/ Percepción
            content += format_amount(taxable_amount, 16, 2, ',')

            # 19 - Alícuota
            content += format_amount(alicuot, 5, 2, ',')

            # 20 - Retención/Percepción Practicada
            content += format_amount(-line.balance, 16, 2, ',')

            # 21 - Monto Total Retenido/Percibido
            content += format_amount(-line.balance, 16, 2, ',')

            content += '\r\n'

            ret_perc += content


        return [{
                'txt_filename': 'Perc/Ret IIBB AGIP Aplicadas.txt',
                'txt_content': ret_perc,
                }, {
                'txt_filename': 'NC Perc/Ret IIBB AGIP Aplicadas.txt',
                'txt_content': credito,
                }]

    def iibb_aplicado_act_7_files_values(self, move_lines):
        return self.iibb_aplicado_files_values(move_lines, act_7=True)

    def iibb_aplicado_files_values(self, move_lines, act_7=None):
        """
        Por ahora es el de arba, renombrar o generalizar para otros
        Implementado segun esta especificacion
        https://drive.google.com/file/d/0B3trzV0e2WzveHhBTk9xWEl6RjA/view
        Implementados:
            - 1.2 Percepciones Act. 7 método Percibido (quincenal)
            - 1.7 Retenciones ( excepto actividad 26, 6 de Bancos y 17 de
            Bancos y No Bancos)
        """
        self.ensure_one()
        ret = ''
        perc = ''

        for line in move_lines:
            # pay_group = payment.payment_group_id
            move = line.move_id
            payment = line.payment_id
            internal_type = line.l10n_latam_document_type_id.internal_type
            document_code = line.l10n_latam_document_type_id.code

            line.partner_id.ensure_vat()

            content = line.partner_id.l10n_ar_formatted_vat
            content += fields.Date.from_string(
                line.date).strftime('%d/%m/%Y')

            # solo para percepciones
            if not payment:
                content += (
                    document_code in ['201', '206', '211'] and 'E' or
                    document_code in ['203', '208', '213'] and 'H' or
                    document_code in ['202', '207', '212'] and 'I' or
                    internal_type == 'invoice' and 'F' or
                    internal_type == 'credit_note' and 'C' or
                    internal_type == 'debit_note' and 'D' or 'R')
                content += line.l10n_latam_document_type_id.l10n_ar_letter
            document_parts = move._l10n_ar_get_document_number_parts(
                move.l10n_latam_document_number, move.l10n_latam_document_type_id.code)
            # si el punto de venta es de 5 digitos no encontramos doc
            # que diga como proceder, tomamos los ultimos 4 digitos
            pto_venta = "{:0>4d}".format(document_parts['point_of_sale'])[-4:]
            nro_documento = "{:0>8d}".format(document_parts['invoice_number'])[-8:]
            content += str(pto_venta)
            content += str(nro_documento)

            # solo para percepciones
            if not payment:
                content += format_amount(-get_line_tax_base(line), 12, 2, ',')

            # este es para el primer tipo de la especificación
            content += format_amount(-line.balance, 11, 2, ',')

            # solo para percepciones
            # según especificación se requiere fecha nuevamente
            # por ahora lo sacamos ya que en ticket 16448 nos mandaron ej.
            # donde no se incluía, en realidad tal vez depende de la actividad
            # ya que en la primer tabla del pdf la agrega y en la segunda no
            if act_7 and not payment:
                content += fields.Date.from_string(
                    line.date).strftime('%d/%m/%Y')
            content += 'A'
            content += '\r\n'

            if payment:
                ret += content
            else:
                perc += content

        # para la fecha de la presentación tomamos la fecha de un apunte a liquidar
        # el valor de la quincena puede ser 0, 1, 2. deberiamos ver si podemos
        # completarlo de alguna manera
        period = move_lines and \
            fields.Date.from_string(move_lines[0].date).strftime('%Y%mX') or ""

        # AR-CUIT-PERIODO-ACTIVIDAD-LOTE_MD5
        perc_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat,
            period,
            "7",  # 7 serian las percepciones
        )

        # AR-vat-PERIODO-ACTIVIDAD-LOTE_MD5
        ret_txt_filename = "AR-%s-%s-%s-LOTEX.txt" % (
            self.company_id.vat,
            period,
            "6",  # 6 serian las retenciones
        )

        return [
            {
                'txt_filename': perc_txt_filename,
                'txt_content': perc,
            },
            {
                'txt_filename': ret_txt_filename,
                'txt_content': ret,
            }]

    def iibb_aplicado_sircar_files_values(self, move_lines):
        """ Especificacion en /doc/sircar
        """
        self.ensure_one()
        ret = ''
        perc = ''

        for line in move_lines.filtered(
                lambda x: not x.payment_id and not x.move_id):
            raise ValidationError(_(
                'Hay lineas a liquidar que no estan enlazadas a pagos ni '
                'facturas lo cual es requerido para generar el TXT'))

        line_nbr = 1
        for line in move_lines.filtered('payment_id'):
            alicuot_line = line.tax_line_id.get_partner_alicuot(
                line.partner_id, line.date)
            if not alicuot_line:
                raise ValidationError(_(
                    'No hay alicuota configurada en el partner '
                    '"%s" (id: %s)') % (
                        line.partner_id.name, line.partner_id.id))

            payment = line.payment_id
            internal_type = line.l10n_latam_document_type_id.internal_type

            # 1 Número de Renglón (único por archivo)
            content = []
            content.append('%05d' % line_nbr)

            # 2 Origen del Comprobante
            content.append('1')

            # 3 Tipo del Comprobante
            if payment.payment_type == 'outbound':
                content.append('1')
            else:
                content.append('2')

            # 4 Número del comprobante
            content.append('%012d' % int(
                re.sub('[^0-9]', '', line.move_id.l10n_latam_document_number or '')))

            # 5 Cuit del contribuyene
            content.append(line.partner_id.ensure_vat())

            # 6 Fecha de la percepción
            content.append(
                fields.Date.from_string(line.date).strftime('%d/%m/%Y'))

            # 7 Monto sujeto a percepción
            content.append(format_amount(
                payment.withholdable_base_amount, 12, 2, '.'))

            # 8 alicuota de la retencion
            content.append(format_amount(
                alicuot_line.alicuota_retencion, 6, 2, '.'))

            # 9 Monto retenido
            content.append(format_amount(-line.balance, 12, 2, '.'))

            # 10 Tipo de Régimen de Percepción
            # (código correspondiente según tabla definida por la jurisdicción)
            if not alicuot_line.regimen_retencion:
                raise ValidationError(_(
                    'No hay regimen de retencion configurado para la alícuota'
                    ' del partner %s') % line.partner_id.name)
            content.append(alicuot_line.regimen_retencion)

            # 11 Jurisdicción: código en Convenio Multilateral de la
            # jurisdicción a la cual está presentando la DDJJ
            if not line.tax_line_id.jurisdiction_code:
                raise ValidationError(_(
                    'No hay etiqueta de jurisdicción configurada!'))

            content.append(line.tax_line_id.jurisdiction_code)

            # Tipo registro 2. Provincia Cordoba
            if line.tax_line_id.jurisdiction_code == '904':

                # 12 Tipo de Operación (1-Efectuada, 2-Anulada, 3-Omitida)
                content.append('2' if internal_type == 'credit_note' else '1')

                # 13 Fecha de Emisión de Constancia (en formato dd/mm/aaaa)
                content.append(fields.Date.from_string(line.date).strftime('%d/%m/%Y'))

                # 14 Número de Constancia - Numeric(14)
                content.append('%014s' % int(re.sub('[^0-9]', '', payment.withholding_number or '0')[:14]))

                # 15 Número de Constancia original (sólo para las Anulaciones –ver códigos por jur-)  - Numeric(14)
                original_invoice = line.move_id._found_related_invoice() or line.move_id
                content.append('%014d' % int(re.sub('[^0-9]', '', original_invoice.document_number or ''))
                               if internal_type == 'credit_note' else '%014d' % 0)

            ret += ','.join(content) + '\r\n'
            line_nbr += 1

        line_nbr = 1
        for line in move_lines.filtered(lambda x: x.move_id.is_invoice()):
            alicuot_line = line.tax_line_id.get_partner_alicuot(
                line.partner_id, line.date)
            if not alicuot_line:
                raise ValidationError(_(
                    'No hay alicuota configurada en el partner '
                    '"%s" (id: %s)') % (
                        line.partner_id.name, line.partner_id.id))


            # 1 Número de Renglón (único por archivo)
            content = []
            content.append('%05d' % line_nbr)

            letter = line.l10n_latam_document_type_id.l10n_ar_letter

            # 2 Tipo de comprobante
            internal_type = line.l10n_latam_document_type_id.internal_type
            if internal_type == 'invoice':
                tipo_comprobante = letter == 'E' and 5 or 1
            elif internal_type == 'credit_note':
                tipo_comprobante = letter == 'E' and 106 or 102
            elif internal_type == 'debit_note':
                tipo_comprobante = letter == 'E' and 6 or 2
            elif line.move_id.type == 'out_invoice':
                tipo_comprobante = 20
            elif line.move_id.type == 'out_refund':
                tipo_comprobante = 120
            else:
                raise ValidationError(_('Tipo de comprobante no reconocido'))
            content.append('%03d' % tipo_comprobante)

            # 3 Letra del comprobante
            content.append(line.l10n_latam_document_type_id.l10n_ar_letter)

            # 4 Número del comprobante
            content.append('%012d' % int(
                re.sub('[^0-9]', '', line.move_id.l10n_latam_document_number or '')))

            # 5 Cuit del contribuyene
            content.append(line.partner_id.ensure_vat())

            # 6 Fecha de la percepción
            content.append(
                fields.Date.from_string(line.date).strftime('%d/%m/%Y'))

            # 7 Monto sujeto a percepción
            content.append(format_amount(-get_line_tax_base(line), 12, 2, '.'))

            # 8 alicuota de la percepcion
            content.append(format_amount(
                alicuot_line.alicuota_percepcion, 6, 2, '.'))

            # 9 Monto percibido
            content.append(format_amount(-line.balance, 12, 2, '.'))

            # 10 Tipo de Régimen de Percepción
            # (código correspondiente según tabla definida por la jurisdicción)
            if not alicuot_line.regimen_percepcion:
                raise ValidationError(_(
                    'No hay regimen de percepcion configurado para la alícuota'
                    ' del partner %s') % line.partner_id.name)
            content.append(alicuot_line.regimen_percepcion)

            # 11 Jurisdicción: código en Convenio Multilateral de la
            # jurisdicción a la cual está presentando la DDJJ
            if not line.tax_line_id.jurisdiction_code:
                raise ValidationError(_(
                    'No hay etiqueta de jurisdicción configurada!'))

            content.append(line.tax_line_id.jurisdiction_code)

            # Tipo registro 2. Provincia Cordoba
            if line.tax_line_id.jurisdiction_code == '904':

                # 12 Tipo de Operación (1-Efectuada, 2-Anulada, 3-Omitida, 4-Informativa)
                content.append('2' if internal_type == 'credit_note' else '1')

                # 13 Número de Constancia original (sólo para 2-Anulaciones) Alfanumérico (14) - ejemplo 1A002311312221
                content.append(self._get_perception_original_invoice_number(line)
                               if internal_type == 'credit_note' else '%014d' % 0)

            perc += ','.join(content) + '\r\n'
            line_nbr += 1

        return [
            {
                'txt_filename': 'Perc IIBB Aplicadas para SIRCAR.txt',
                'txt_content': perc,
            },
            {
                'txt_filename': 'Ret IIBB Aplicadas para SIRCAR.txt',
                'txt_content': ret,
            }]

    def iibb_sufrido_files_values(self, move_lines):
        """
        Especificación según:
        https://drive.google.com/file/d/0B3trzV0e2WzvUjB1MnhXT0VteFE/view
        y ej. de excel acá
        http://www.ca.gov.ar/descargar/sifere/importaciones_sifere.xls

        tal vez querramos agregar chequeo de que es "sifere" viendo que es
        cia multilateral
        """
        self.ensure_one()

        ret = ''
        perc = ''
        desp_imp = ''
        for line in move_lines:
            if line.l10n_latam_document_type_id.code in ['66', '67']:
                desp_imp += ' - ' + line.move_id.display_name + '\n'
                continue
            payment = line.payment_id
            # pay_group = payment.payment_group_id
            move = line.move_id
            internal_type = line.l10n_latam_document_type_id.internal_type

            line.partner_id.ensure_vat()

            content = line.tax_line_id.jurisdiction_code or '000'
            content += line.partner_id.l10n_ar_formatted_vat
            content += fields.Date.from_string(
                line.date).strftime('%d/%m/%Y')

            # en las retenciones, el numero de comprobante debe ser de 16
            # digitos y ademas sacamos estos datos del pago y no del nro de doc
            # del payment group
            if payment:
                # el numero de la retencion
                pos, number = get_pos_and_number(payment.withholding_number)
                content += '{:>04s}'.format(pos)
                content += '{:>016s}'.format(number)
            else:
                document_parts = move._l10n_ar_get_document_number_parts(
                    move.l10n_latam_document_number, move.l10n_latam_document_type_id.code)
                pos = document_parts['point_of_sale']
                number = document_parts['invoice_number']
                # si el punto de venta es de 5 digitos no encontramos doc
                # que diga como proceder, tomamos los ultimos 4 digitos
                pto_venta = "{:0>4d}".format(document_parts['point_of_sale'])[-4:]
                nro_documento = "{:0>8d}".format(document_parts['invoice_number'])[-8:]
                content += pto_venta
                content += nro_documento

            # si es pago es R, si no es la letra del comprobante u Otros
            if payment:
                content += 'R'
                # la letra tiene que ser A, B, C, E, M ó bien Espacio, en caso
                # de pago tenemox X, mandamos espacio
                content += ' '
            else:
                # por lo que vimos en sos-contador, si es ticket se pasa
                # como factura
                doc_type = (
                    internal_type in ['invoice', 'ticket'] and 'F' or
                    internal_type == 'credit_note' and 'C' or
                    internal_type == 'debit_note' and 'D' or
                    internal_type == 'receipt_invoice' and 'R' or 'O')
                # si es ticket y es negativo entonces en NC (TODO) cambiar
                # si ya implementamos nc de ticket de otra manera
                if internal_type == 'ticket' and line.balance < 0.0:
                    doc_type = 'credit_note'
                content += doc_type
                if doc_type == 'O':
                    content += ' '
                else:
                    content += (
                        line.l10n_latam_document_type_id.l10n_ar_letter or ' ')

            # en retencíones hay que poner el número de comprobante original
            # pero solo en digitos
            if payment:
                content += '%020d' % int(
                    re.sub('[^0-9]', '', move.l10n_latam_document_number))
            content += format_amount(line.balance, 11, 2, ',')
            content += '\r\n'

            if payment:
                ret += content
            else:
                perc += content

        if desp_imp:
            desp_imp = ('En los registros seleccionados encontramos algunos despachos de importación, los mismos deben'
                        'cargarse a mano. Los registros despachos corrspondientes son:\n') + desp_imp
        return [
            {
                'txt_filename': 'Percepciones sufridas SIFERE.txt',
                'txt_content': perc,
            }, {
                'txt_filename': 'Retenciones sufridas SIFERE.txt',
                'txt_content': ret,
            }, {
                'txt_filename': 'Despachos de importación (no importar).txt',
                'txt_content': desp_imp,
            }]

    def sicore_aplicado_files_values(self, move_lines):
        self.ensure_one()

        # build txt file
        content = ''

        for line in move_lines.sorted(key=lambda r: (r.date, r.id)):
            partner = line.partner_id
            if not partner.l10n_latam_identification_type_id.l10n_ar_afip_code:
                raise ValidationError(_(
                    'EL tipo de identificación "%s" no tiene código de afip'
                    'configurado') % (partner.l10n_latam_identification_type_id.name))
            if not partner.vat:
                raise ValidationError(_(
                    'El partner "%s" (id %s) no tiene número de identificación '
                    'seteada') % (partner.name, partner.id))

            payment = line.payment_id
            pay_group = payment.payment_group_id
            move = line.move_id

            #si tengo payment es una retención, sino es una percepción y tengo que sacar la información de la factura (del move)
            if payment:
                # Codigo del Comprobante         [ 2]
                content += (payment.payment_type == 'inbound' and '02') or (
                    payment.payment_type == 'outbound' and '06') or '00'

                # Fecha Emision Comprobante      [10] (dd/mm/yyyy)
                content += fields.Date.from_string(
                    pay_group.payment_date).strftime('%d/%m/%Y')
                # Numero Comprobante            [16]
                content += '%016d' % int(re.sub('[^0-9]', '', move.l10n_latam_document_number))
                #Importe del comprobante
                codop = '1'
                issue_date = payment.payment_date
                amount_tot = abs(payment.payment_group_id.payments_amount)
                base_amount = payment.withholdable_base_amount

            elif move.is_invoice():
                # Codigo del Comprobante         [ 2]
                tipodoc = int(move.l10n_latam_document_type_id.code)

                if tipodoc in [1, 6, 19, 51, 81, 82, 118, 201, 206]:
                    # Factura
                    content += '01'
                elif tipodoc in [4, 9, 54]:
                    # Recibo
                    content += '02'
                elif tipodoc in [3, 8, 21, 53, 43, 44, 110, 112, 113, 114, 119, 203, 208]:
                    # Nota de Crédito
                    content += '03'
                elif tipodoc in [2, 7, 20, 52, 45, 46, 115, 116, 120, 202, 207]:
                    # Nota de Débito
                    content += '04'
                else:
                    # Otro comprobante
                    content += '05'

                # Fecha Emision Comprobante      [10] (dd/mm/yyyy)
                content += fields.Date.from_string(
                    move.invoice_date).strftime('%d/%m/%Y')
                # Numero Comprobante            [16]
                # content += '%016d' % int(re.sub('[^0-9]', '', move.l10n_latam_document_number))
                content += '%05d' % int(re.sub('[^0-9]', '', move.l10n_latam_document_number)[:5])
                content += '%011d' % int(re.sub('[^0-9]', '', move.l10n_latam_document_number)[11:])
                issue_date = move.invoice_date
                base_amount = line.tax_base_amount
                codop = '2'
                #Importe del comprobante
                amount_tot = abs(move.amount_total_signed)

            # Importe Comprobante            [16]
            content += '%016.2f' % amount_tot
            # Codigo de Impuesto             [ 4]
            # Codigo de Regimen              [ 3]
            if line.tax_line_id.tax_group_id == self.env.ref('l10n_ar_ux.tax_group_retencion_ganancias'):
                content += '0217'
                regimen = pay_group.regimen_ganancias_id
                # necesitamos lo de filter porque hay dos regimenes que le
                # agregamos caracteres
                content += regimen and '%03d' % int(''.join(filter(
                    str.isdigit, str(regimen.codigo_de_regimen)))) or '000'
            elif line.tax_line_id.tax_group_id == self.env.ref('l10n_ar_ux.tax_group_retencion_iva'):
                content += '0767'
                # por ahora el unico implementado es para factura M
                content += '%03d' % int(line.tax_line_id.codigo_regimen) if line.tax_line_id.codigo_regimen else '499'
            elif line.tax_line_id.tax_group_id == self.env.ref('l10n_ar.tax_group_percepcion_iva'):
                content += '0767'
                content +=  '%03d' % int(line.tax_line_id.codigo_regimen) # (ver account tax) DUDA cómo le aplico el código de régimen a las facturas viejas
            else:
                raise ValidationError(_('Grupos de impuestos %s no implementados para SICORE') % line.tax_line_id.tax_group_id.name)

            # Codigo de Operacion            [ 1]
            content += codop  # TODO: ???? DUDA: SERÍA PARA VER SI ES RETENCION O PERCEPCION

            # Base de Calculo                [14]
            content += '%014.2f' % base_amount

            # Fecha Emision Retencion        [10] (dd/mm/yyyy)
            content += fields.Date.from_string(issue_date).strftime('%d/%m/%Y')

            # Codigo de Condicion            [ 2]
            content += '01'  # TODO: ???? ver tabla de condición sicore

            # Retención Pract. a Suj. ..     [ 1]
            content += '0'  # TODO: ????

            # Importe de Retencion           [14] (también se usa para importe de percepción)
            content += '%014.2f' % abs(line.balance)

            # Porcentaje de Exclusion        [ 6]
            content += '%06.2f' % line.tax_line_id.porcentaje_exclusion or '000.00'

            # Fecha Emision Boletin          [10] (dd/mm/yyyy)
            content += fields.Date.from_string(
                issue_date).strftime('%d/%m/%Y')

            # Tipo Documento Retenido        [ 2]
            content += '%02d' % int(partner.l10n_latam_identification_type_id.l10n_ar_afip_code)

            # Numero Documento Retenido      [20]
            content += partner.vat.ljust(20)

            # Numero Certificado Original    [14]
            content += '%014d' % 0  # TODO: ????

            content += '\r\n'

        return [{
            'txt_filename': 'SICORE Aplicado.txt',
            # 'txt_filename': 'SICORE_%s_%s_%s.txt' % (
            #     re.sub(r'[^\d\w]', '', self.company_id.name),
            #     self.from_date, self.to_date),
            'txt_content': content,
        }]
