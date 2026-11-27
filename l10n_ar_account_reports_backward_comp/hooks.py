EARNINGS_APPLIED_XMLID_NAMES = (
    "ri_tax_retencion_ganancias_aplicada",
    "ri_tax_withholding_ganancias_applied",
)


def post_init_hook(env):
    # Archive the earnings withholding tax migrated from the previous version, as an active one
    # with is_backward_tax would be treated as created in the new version.
    companies = env["res.company"].search(
        [("chart_template", "in", ("ar_base", "ar_ri", "ar_ex")), ("parent_id", "=", False)]
    )
    xmlid_names = [f"{company.id}_{name}" for company in companies for name in EARNINGS_APPLIED_XMLID_NAMES]
    xmlids = env["ir.model.data"].search([("model", "=", "account.tax"), ("name", "in", xmlid_names)])
    taxes = env["account.tax"].with_context(active_test=False).browse(xmlids.mapped("res_id")).exists()
    taxes.filtered(lambda tax: tax.active or not tax.is_backward_tax).write({"is_backward_tax": True, "active": False})
