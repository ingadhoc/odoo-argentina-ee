import re

from odoo import _, fields, models
from odoo.addons.l10n_ar_account_tax_settlement.models.account_journal import remove_accents_and_dieresis
from odoo.exceptions import RedirectWarning, UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    settlement_tax = fields.Selection(
        selection_add=[
            ("sire", "TXT Retenciones SIRE"),
            ("certificado_retencion_impositiva", "TXT Certificado Retención Impositiva"),
        ]
    )

    def sire_files_values(self, move_lines):
        """Devuelve contenido del archivo Retenciones_sire.txt . Implementado según especificación de tarea 40906.
        https://www.afip.gob.ar/sire/documentos/SIRE-especificacion-para-emision-por-lote.pdf apartado 3.
        F2003 CERTIFICADOS SUJETOS DOMICILIADOS EN EL EXTERIOR.
        También se puede ver la especificación en doc/SIRE-especificacion-para-emision-por-lote.pdf"""
        self.ensure_one()
        content = ""
        # VALIDACIONES
        self._sire_validations(move_lines)
        for line in move_lines.sorted(key=lambda r: (r.date, r.id)):
            payment = line.payment_id
            pais = line.partner_id.country_id
            es_persona = line.partner_id.company_type == "person"
            company_vat = payment.company_id.vat

            fecha_impuesto = line.date.strftime("%d/%m/%Y")
            # 1 Formulario (integer long 4, 1-4, obligatorio) --> '2003' task 40050 agi 2024.10.23 10:00hs
            # Además en la sección "3.2. F2003 - Validaciones", pàgina 5 del pdf de la especificación se indica que
            # debe ser fijo "2003"
            content += "2003"
            # 2 Versión (integer long 4, 5-8, obligatorio) --> '0100' task 40050 agi comment 2024.10.23 10:00hs
            # Además en la sección "3.2. F2003 - Validaciones", pàgina 5 del pdf de la especificación se indica que debe
            # ser fijo "0100"
            content += "0100"
            # 3 Código de trazabilidad (string long 10, 9-18, no obligatorio) --> texto libre o en blanco -->
            # task 40050 agi 2024.10.23 10:00hs
            content += " " * 10
            # 4 Cuit agente (integer, long 11, 19-29, obligatorio)
            content += company_vat
            # 5 Impuesto (integer long 3, 30-32, no obligatorio) -->
            # sección "3.2. F2003 - Validaciones", pàgina 5 del pdf de la especificación se indica que debe ser
            # fijo "218"
            content += "218"
            # 6 Régimen (integer long 3, 33-35, obligatorio)
            tax = line._get_settlement_tax()
            content += tax.l10n_ar_code.zfill(3)
            # 7 Cuit ordenante (integer 11, 36-46, obligatorio)
            content += company_vat
            # 8 Fecha retención (date long 10, 59-68, obligatorio)
            content += fecha_impuesto
            # 9 Tipo comprobante (integer 2, 57-58, obligatorio)
            # por el momento lo dejamos fijo '06' que es el tipo de comprobante para retenciones
            # pero en un futuro para percepciones puede tomar otros valrores (tomar como referencia lo desarrollado
            # para sicore)
            # --> ver espeficiación vieja tarea 40906
            content += "06"
            # 10 Fecha comprobante (date 10, 59-68, obligatorio)
            content += fecha_impuesto
            # 11 Nro comprobante (string 16, 69-84, obligatorio)
            # Número de Orden de Pago sin guiones ni tipo de identificación (ej: 000100008220)
            # (prefijo sin - + número de documento)
            # (no es obligatorio) --> ver espeficiación vieja tarea 40906
            content += re.sub("[^0-9]", "", payment.name).ljust(16)
            # 12 Importe comprobante (decimal 14, 85-98, obligatorio)
            content += "%14.2f" % payment.payment_total
            # 13 Filler (filler 14, 99-112, obligatorio)
            content += " " * 14
            # 14 Certificado original nro (string 25, 113-137, no obligatorio)
            content += " " * 25
            # 15 Certificado original fecha reten (date 10, 138-147, no obligatorio)
            content += " " * 10
            # 16 Certificado original importe (decimal 14, 148-161, no obligatorio)
            content += " " * 14
            # 17 Motivo emisión nota de créditon(string 30, 162-191, no obligatorio)
            content += " " * 30
            # 18 No retención (boolean 1, 192-192, obligatorio) --> ver especificación vieja tarea 40906
            content += "0"
            # 19 No retención motivo (string 30, 193-222, no obligatorio)
            content += "0" * 30
            # 20 Aplica CDI (boolean 1, 223-223, obligatorio) --> especificación 40906, mt 11/12/24
            content += "1" if payment.sire_aplica_cdi else "0"
            # 21 Código de alícuota (integer, 4, 224-227, obligatorio)
            content += payment.sire_codigo_alicuota.zfill(4)
            # 22 Aplica acrecentamiento (boolean, 1, 228-228)
            content += "1" if payment.sire_aplica_acrecentamiento else "0"
            # 23 Retenido clave nif (string 50, 229-278, obligatorio)
            # Cuit del pais del sujeto retenido s/ especificación tarea 40906, mt 11/12/24
            content += pais.l10n_ar_natural_vat if es_persona else pais.l10n_ar_legal_entity_vat
            content += " " * 39
            # 24 Retenido Apellido Nombre Denominacion (string, 60, 279-338, obligatorio)
            content += line.partner_id.name[:60].ljust(60)
            # 25 Retenido domicilio actual en exterior (string, 60, 339-398, obligatorio)
            # domicilio completo --> task 40050 agi 2024.10.23 10:00hs
            domicilio = " ".join(
                item
                for item in [
                    payment.partner_id.street,
                    payment.partner_id.street2,
                    payment.partner_id.city,
                    payment.partner_id.state_id.name if payment.partner_id.state_id else None,
                ]
                if item
            )
            content += domicilio[:60].ljust(60) if domicilio else " " * 60
            # 26 Retenido domicilio actual en exterior pais (integer, 3, 399-401, obligatorio)
            content += line.partner_id.country_id.l10n_ar_afip_code or " " * 3
            # 27 Retenido tipo de persona (string, 1, 402-402, obligatorio)
            content += "F" if es_persona else "J"
            # 28 Retenido nacimiento constitucion pais (integer, 3, 403-405, no obligatorio)
            content += (
                line.partner_id.sire_born_country_id.l10n_ar_afip_code
                if es_persona and line.partner_id.sire_born_country_id
                else " " * 3
            )
            # 29 Retenido nacimiento constitucion fecha (date 10, 406-415, no obligatorio)
            content += (
                line.partner_id.sire_birthdate.strftime("%d/%m/%Y")
                if es_persona and line.partner_id.sire_birthdate
                else " " * 10
            )
            content += "\r\n"
        return [{"txt_filename": "Retenciones_sire.txt", "txt_content": remove_accents_and_dieresis(content)}]

    def _sire_validations(self, move_lines):
        """Validaciones para el archivo TXT Retenciones SIRE. Si no hay errores este método no
        devuelve nada, de lo contrario se lanzará mensaje de error que corresponda indicando lo que el usuario debe
        corregir para poder generar el archivo."""
        # Validamos que el impuesto SIRE tenga código de régimen establecido
        for line in move_lines.sorted(key=lambda r: (r.date, r.id)):
            tax = line._get_settlement_tax()
            if not tax.l10n_ar_code:
                raise RedirectWarning(
                    message=_(
                        "El impuesto '%(tax_name)s' (id: %(tax_id)s) no tiene código de régimen establecido. Es obligatorio para generar el"
                        " archivo txt Sire. Editar campo 'Codigo AFIP' (l10n_ar_code) en la vista formulario del impuesto.",
                        tax_id=tax.id,
                        tax_name=tax.name,
                    ),
                    action=tax.get_formview_action(),
                    button_text=_("Editar impuesto"),
                )

            # Validamos que el partner sea Cliente / Proveedor del Exterior
            if line.partner_id.l10n_ar_afip_responsibility_type_id.id not in [
                self.env.ref("l10n_ar.res_EXT").id,
                self.env.ref("l10n_ar.res_EXT_Prov").id,
            ]:
                raise RedirectWarning(
                    message=_(
                        "Solo puede generar el archivo de retenciones SIRE para contactos con responsabilidad"
                        " AFIP: 'Cliente / Proveedor del Exterior'. Contacto: %(name)s (id: %(id)s)",
                        name=line.partner_id.name,
                        id=line.partner_id.id,
                    ),
                    action=line.partner_id.get_formview_action(),
                    button_text=_("Editar contacto"),
                )

            # Validamos que el contacto tenga país establecido
            if not line.partner_id.country_id:
                raise RedirectWarning(
                    message=_("El contacto '%s' debe tener país establecido", line.payment_id.partner_id.name),
                    action=line.partner_id.get_formview_action(),
                    button_text=_("Editar contacto"),
                )

            # Validamos que el país del contacto tenga el cuit correspondiente
            pais = line.partner_id.country_id
            es_persona = line.partner_id.company_type == "person"
            if es_persona and not pais.l10n_ar_natural_vat:
                raise RedirectWarning(
                    message=_("El país '%s' no tiene IVA Persona Física establecido.", pais.name),
                    action=pais.get_formview_action(),
                    button_text=_("Editar País"),
                )
            if not es_persona and not pais.l10n_ar_legal_entity_vat:
                raise RedirectWarning(
                    message=_("El país '%s' no tiene cuit persona jurídica establecido.", pais.name),
                    action=pais.get_formview_action(),
                    button_text=_("Editar País"),
                )

            # Validamos que el código de alícuota se encuentre entre 1 y 83 si no aplica CDI
            if not line.payment_id.sire_aplica_cdi and int(line.payment_id.sire_codigo_alicuota) > 83:
                raise UserError(
                    _(
                        "El pago %(payment_name)s (id: %(payment_id)s) debe tener código de alícuota"
                        " menor a 83 ya que no aplica CDI",
                        payment_name=line.payment_id.name,
                        payment_id=line.payment_id.id,
                    )
                )

    def certificado_retencion_impositiva_files_values(self, move_lines):
        """Devuelve contenido del archivo Retenciones_sire.txt .Implementado según especificación de tarea 40906.
        https://www.afip.gob.ar/sire/documentos/SIRE-especificacion-para-emision-por-lote.pdf apartado 5.
        F2005 CERTIFICADOS DE RETENCIÓN IMPOSITIVA. También se puede ver la especificación en
        doc/SIRE-especificacion-para-emision-por-lote.pdf . (beta: nunca fue testeado) ."""
        self.ensure_one()
        content = ""
        for line in move_lines.sorted(key=lambda r: (r.date, r.id)):
            payment = line.payment_id
            tax = line._get_settlement_tax()
            if not tax.l10n_ar_code:
                raise RedirectWarning(
                    message=_(
                        "El impuesto '%s' no tiene código de régimen establecido."
                        " Editar campo 'Codigo de regimen IVA' en solapa 'Opciones avanzadas'"
                        "en la vista formulario",
                        tax.name,
                    ),
                    action={
                        "type": "ir.actions.act_window",
                        "res_model": "account.tax",
                        "views": [(False, "form")],
                        "res_id": tax.id,
                        "name": _("Tax"),
                        "view_mode": "form",
                    },
                    button_text=_("Editar impuesto"),
                )
            fecha_impuesto = fields.Date.from_string(line.date).strftime("%d/%m/%Y")
            # 1 Versión (integer long 4, 1-4, obligatorio) --> 0100
            content += "0100"
            # 2 Código de trazabilidad (string long 36, 5-40, no obligatorio)
            content += " " * 36
            # 3 Impuesto (integer long 3, 41-43, obligatorio)
            content += "216"
            # 4 Régimen (integer long 3, 44-46, obligatorio)

            content += tax.l10n_ar_code
            # 5 Fecha retención (date long 10, 47-56, obligatorio)
            content += fecha_impuesto
            # 6 Condición (integer 2, 57-58, no obligatorio)
            content += " " * 2
            # 7 Imposibilidad de retención (boolean long 1, 59-59, obligatorio)
            content += "0"
            # 8 No retención motivo (string 30, 60-89, no obligatorio)
            content += " " * 30
            # 9 Importe retención (decimal 14, 90-103, obligatorio)
            content += "%014.2f" % abs(line.balance)
            # 10 Importe de la base de cálculo/cantidad (decimal 14, 104-117, obligatorio)
            content += "%014.2f" % abs(line.withholding_id.base_amount)
            # 11 Régimen de exclusión (boolean 1, 118-118, obligatorio)
            content += "0"
            # 12 Porcentaje de exclusión (decimal 6, 119-124, no obligatorio)
            content += "%06.2f" % tax.porcentaje_exclusion if tax.porcentaje_exclusion != "0.0" else "000.00"
            # 13 Fecha publicación o finalización de la vigencia (date 10, 125-134, no obligatorio)
            content += " " * 10
            # 14 Tipo comprobante (integer 2, 135-136, obligatorio)
            # por el momento lo dejamos fijo '06' que es el tipo de comprobante para retenciones
            # pero en un futuro para percepciones puede tomar otros valrores (tomar como referencia lo desarrollado
            # para sicore)
            content += "06"
            # 15 Fecha comprobante (date 10, 137-146, obligatorio)
            content += fecha_impuesto
            # 16 Nro comprobante (string 16, 147-162, no obligatorio)
            content += re.sub("[^0-9]", "", payment.name).ljust(16)
            # 17 COE (string 12, 163-174, no obligatorio)
            content += " " * 12
            # 18 COE ORIGINAL (string 12, 175-186, no obligatorio)
            content += " " * 12
            # 19 CAE (string 14, 187-200, no obligatorio)
            content += " " * 14
            # 20 Importe comprobante (decimal 14, 201-214, obligatorio)
            content += "%14.2f" % payment.payment_total
            # 21 Motivo emisión de nota de crédito/ajuste (string 30, 215-244, no obligatorio)
            content += " " * 30
            # 22 Retenido clave (integer 11, 245-255, obligatorio)
            # Si es cliente del exterior establecemos cuit del país del exterior, sino establecemos l10n_ar_vat
            if line.partner_id.l10n_ar_afip_responsibility_type_id.id == self.env.ref("l10n_ar.res_EXT").id:
                pais = line.partner_id.country_id
                if not pais.l10n_ar_legal_entity_vat:
                    raise RedirectWarning(
                        message=_("El país '%s' no tiene cuit persona jurídica establecido.", pais.name),
                        action={
                            "type": "ir.actions.act_window",
                            "res_model": "res.country",
                            "views": [(False, "form")],
                            "res_id": pais.id,
                            "name": _("País"),
                            "view_mode": "form",
                        },
                        button_text=_("Editar País"),
                    )
                content += pais.l10n_ar_legal_entity_vat
            else:
                content += line.partner_id.l10n_ar_vat
            # 23 Certificado original nro (string 25, 256-280, no obligatorio)
            content += " " * 25
            # 24 Certificado original fecha reten (date 10, 281-290, no obligatorio)
            content += " " * 10
            # 25 Certificado original importe (decimal 14, 291-304, no obligatorio)
            content += " " * 14
            # 26 Motivo de la anulación (integer 1, 305-305, no obligatorio)
            content += " " * 1
            content += "\r\n"
        return [
            {
                "txt_filename": "Retenciones_sire.txt",
                "txt_content": content,
            }
        ]
