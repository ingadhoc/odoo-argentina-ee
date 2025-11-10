import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartnerUpdateFromPadronField(models.TransientModel):
    _inherit = "res.partner.update.from.padron.field"


class ResPartnerUpdateFromPadronWizard(models.TransientModel):
    _inherit = "res.partner.update.from.padron.wizard"

    update_constancia = fields.Boolean(
        default=True,
    )

    def get_partner_data(self, partner):
        """Implementación específica para AFIP"""
        return partner.get_data_from_padron_afip()

    @api.model
    def get_partners(self):
        """Busca partners con CUIT válido para Argentina"""
        domain = [("vat", "!=", False), ("l10n_latam_identification_type_id.l10n_ar_afip_code", "=", 80)]
        active_ids = self._context.get("active_ids", [])
        if active_ids:
            domain.append(("id", "in", active_ids))
        return self.env["res.partner"].search(domain)

    @api.model
    def default_get(self, fields):
        country_code = self.env["res.partner"].browse(self._context.get("active_ids")).country_id.code
        if country_code == "AR":
            res = super(ResPartnerUpdateFromPadronWizard, self).default_get(fields)
            context = self._context
            if context.get("active_model") == "res.partner" and context.get("active_ids"):
                partners = self.get_partners()
                if not partners:
                    raise UserError(_("No se encontró ningún partner con CUIT para actualizar"))
            return res
        return super().default_get(fields)

    @api.model
    def _get_domain(self):
        """Define campos específicos de Argentina/AFIP"""
        fields_names = [
            "name",
            "estado_padron",
            "street",
            "city",
            "zip",
            "actividades_padron",
            "impuestos_padron",
            "state_id",
            "actividad_monotributo_padron",
            "empleador_padron",
            "integrante_soc_padron",
            "last_update_padron",
            "l10n_ar_afip_responsibility_type_id",
        ]
        return [("model", "=", "res.partner"), ("name", "in", fields_names)]

    @api.model
    def _get_default_title_case(self):
        """Configuración específica para Argentina"""
        parameter = self.env["ir.config_parameter"].sudo().get_param("use_title_case_on_padron_afip")
        if parameter == "False" or parameter == "0":
            return False
        return True

    def _get_many2one_fields(self):
        """Campos Many2one específicos de Argentina"""
        return ["state_id", "l10n_ar_afip_responsibility_type_id"]

    def _get_many2many_fields(self):
        """Campos Many2many específicos de Argentina"""
        return ["impuestos_padron", "actividades_padron"]

    def _post_update_hook(self):
        """Actualización de constancia específica de Argentina"""
        if self.update_constancia:
            self.partner_id.update_constancia_from_padron_afip()

    def _get_error_message(self, error):
        """Mensaje de error personalizado para AFIP"""
        return f"Falló actualización AFIP: {error}"


class ResPartnerUpdateFromPadronInfo(models.TransientModel):
    _inherit = "res.partner.update.from.padron.info"
