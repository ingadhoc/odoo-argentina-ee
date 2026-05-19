from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Remove deprecated onboarding and onboarding steps"""

    # Remove onboarding steps
    onboarding_steps = [
        "account_balance_import.onboarding_onboarding_initial_balance_step",
        "account_balance_import.onboarding_onboarding_initial_check_balance_step",
        "account_balance_import.onboarding_onboarding_initial_partner_balance_step",
    ]

    for step_xmlid in onboarding_steps:
        step = env.ref(step_xmlid, raise_if_not_found=False)
        if step:
            step.unlink()

    # Remove onboarding (if exists)
    onboarding = env.ref("account_balance_import.onboarding_onboarding", raise_if_not_found=False)
    if onboarding:
        onboarding.unlink()
