from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_post(self):
        """Al validar el pago, si la compañia tiene modo automatico para informar
        retenciones, y tiene lineas de retencion arba entonces enviamos a ARBA
        el resultado es que vamos a tener el campo certificado con el numero
        asignado por ARBA para cada linea de retencion informada.
        """
        res = super().action_post()
        for payment in self:
            # Solo si la compañia tiene modo automatico de retenciones ARBA entonces
            # informamos a ARBA, sino continuamos
            if payment.company_id.l10n_ar_arba_wh_mode != "automatic":
                continue

            # Filtramos solo las lineas asociadas a retencion de arba que no tengan
            # numero de certificado aun (no informadas)
            wh_lines = payment.l10n_ar_withholding_line_ids.filtered(
                lambda x: x.is_arba_ws_needed and not x.l10n_ar_cert_number
            )
            wh_lines.send_to_arba()
        return res

    def action_draft(self):
        """Verificar si hay retenciones informadas a ARBA antes de volver a borrador.
        Si hay retenciones informadas, mostrar un warning."""
        # Verificar si debemos mostrar el warning (solo si no viene del wizard)
        if not self.env.context.get("skip_arba_draft_warning"):
            for payment in self:
                # Buscar retenciones que ya fueron informadas a ARBA
                wh_lines = payment.l10n_ar_withholding_line_ids.filtered(
                    lambda x: x.is_arba_ws_needed and x.l10n_ar_cert_number and x.l10n_ar_dj_arba_id
                )

                if wh_lines:
                    # Generar información HTML de las retenciones
                    wh_info_html = "<ul>"
                    for wh in wh_lines:
                        wh_info_html += (
                            f"<li><strong>{wh.name}</strong> - "
                            f"Certificate: {wh.l10n_ar_cert_number} - "
                            f"DDJJ: {wh.l10n_ar_dj_arba_id.display_name} "
                            f"(Amount: ${wh.amount:,.2f})</li>"
                        )
                    wh_info_html += "</ul>"

                    # Crear el wizard con el warning
                    wizard = self.env["arba.withholding.draft.warning"].create(
                        {
                            "payment_id": payment.id,
                            "withholding_count": len(wh_lines),
                            "withholding_info": wh_info_html,
                        }
                    )

                    return {
                        "name": "Warning - ARBA Withholdings",
                        "type": "ir.actions.act_window",
                        "res_model": "arba.withholding.draft.warning",
                        "res_id": wizard.id,
                        "view_mode": "form",
                        "target": "new",
                    }

        return super().action_draft()
