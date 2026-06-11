from odoo import models


class OnboardingOnboarding(models.Model):
    _inherit = "onboarding.onboarding"

    def _prepare_rendering_values(self):
        if not self.current_progress_id:
            self.sudo()._search_or_create_progress()
        return super()._prepare_rendering_values()
