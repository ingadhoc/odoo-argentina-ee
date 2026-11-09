import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class L10nArPaymentWithholding(models.Model):
    _inherit = "l10n_ar.payment.withholding"

    l10n_ar_cert_number = fields.Char(readonly=True, string="ARBA Withholding Certificate Number")
    l10n_ar_dj_arba_id = fields.Many2one(
        "l10n_ar.dj.arba", "DDJJ ARBA", help="ARBA DDJJ associated with this withholding"
    )
    l10n_ar_arba_wh_mode = fields.Selection(
        related="company_id.l10n_ar_arba_wh_mode",
        string="ARBA Withholding Mode",
    )
    l10n_ar_state_id = fields.Many2one(related="tax_id.l10n_ar_state_id")
    is_arba_ws_needed = fields.Boolean(
        compute="_compute_is_arba_ws_needed",
        string="It needs to be sent to the ARBA A122R webservice",
        help="Only applies to incurred withholding for ARBA on taxes with type supplier payments",
    )

    def _compute_is_arba_ws_needed(self):
        """Verifica si la retención debe ser informada a ARBA.
        True si cumple con las condiciones:
        - Es de la jurisdicción de Buenos Aires (ARBA)
        - Es de tipo retención de pago a proveedor
        """
        state_ar_b = self.env.ref("base.state_ar_b", raise_if_not_found=False)
        for rec in self:
            rec.is_arba_ws_needed = (
                state_ar_b
                and rec.tax_id.l10n_ar_state_id == state_ar_b
                and rec.tax_id.l10n_ar_withholding_payment_type == "supplier"
            )

    def send_to_arba(self):
        """Send the withholding to ARBA webservice and store the certificate number"""
        for withholding in self.filtered(lambda x: not x.l10n_ar_cert_number and x.amount > 0):
            withholding.l10n_ar_dj_arba_id._create_withholding(withholding)

    def _send_to_arba_after_commit(self):
        """Send the withholdings to ARBA only once the current transaction is committed.
        ARBA keeps the withholding even if the transaction is rolled back afterwards, and the next
        attempt goes with another number, so ARBA would end up with a second one."""
        env, wh_ids = self.env, self.ids

        def send_to_arba():
            with env.registry.cursor() as cr:
                for withholding in env(cr=cr)[self._name].browse(wh_ids).exists():
                    try:
                        with cr.savepoint():
                            withholding.send_to_arba()
                    except Exception as exp:
                        # The payment is already posted: leave the error where the user can retry
                        _logger.exception("ARBA WS ERROR sending withholding %s", withholding.id)
                        withholding.payment_id.message_post(
                            body=withholding.env._("ERROR trying to inform the withholding: ") + str(exp)
                        )

        self.env.cr.postcommit.add(send_to_arba)
