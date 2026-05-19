from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    if env["ir.model.fields.selection"].search([("field_id.model", "=", "account_balance_import")]):
        env.cr.execute(
            "delete from ir_model_fields_selection where id in %s",
            (tuple(env["ir.model.fields.selection"].search([("field_id.model", "=", "account_balance_import")]).ids),),
        )
