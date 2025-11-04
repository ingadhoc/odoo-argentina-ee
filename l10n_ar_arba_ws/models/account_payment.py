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
            # TODO mejorar la forma de calcular las lineas de retencion de arba
            state_ar_b = self.env.ref("base.state_ar_b")
            wh_lines = payment.l10n_ar_withholding_line_ids.filtered(
                lambda x: (x.tax_id.l10n_ar_state_id == state_ar_b and not x.l10n_ar_cert_number)
            )
            wh_lines.send_to_arba()
        return res
