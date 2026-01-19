from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        """Hacemos que algunos reportes argentinos queden en borrador.
        Retornamos False para los asientos de cierre de returns argentinos cuando se llama desde el return,
        evitando que se posteen automáticamente.
        """
        if self._context.get("post_from_tax_return"):
            ar_closing_types = [
                self.env.ref("l10n_ar_account_reports.ar_sifere_iibb_return_type", raise_if_not_found=False),
                self.env.ref("l10n_ar_reports.ar_tax_return_type", raise_if_not_found=False),
            ]
            ar_closing_types = [t for t in ar_closing_types if t]  # Filtrar None
            moves_to_skip = self.filtered(
                lambda m: m.company_id.country_id.code == "AR" and m.closing_return_id.type_id in ar_closing_types
            )
            if moves_to_skip == self:
                # Todos los moves son de cierre AR, no posteamos ninguno
                return False
            # Postear solo los que no son de cierre AR
            return super(AccountMove, self - moves_to_skip).action_post()
        return super().action_post()

    def _post(self, soft=True):
        """Extendemos _post para recalcular montos en returns argentinos después del posteo."""
        posted = super()._post(soft=soft)
        # Recalcular montos a pagar cuando se postea un asiento de cierre argentino
        # (principalmente para los returns que se entregan en borrador y el usuario postea manualmente pero igual
        # lo hacemos para todos los posteos por si acaso).
        for move in self.filtered(lambda x: x.closing_return_id and x.company_id.country_id.code == "AR"):
            account_return = move.closing_return_id
            payable_accounts, receivable_accounts = account_return._get_tax_closing_payable_and_receivable_accounts()
            account_return.period_amount_to_pay = (
                account_return._evaluate_period_amount_to_pay_from_tax_closing_accounts(
                    payable_accounts, receivable_accounts
                )
            )
            account_return.total_amount_to_pay = account_return._evaluate_total_amount_to_pay_from_tax_closing_accounts(
                payable_accounts, receivable_accounts
            )
        return posted
