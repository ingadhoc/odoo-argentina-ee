##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval as eval


class database(models.Model):
    _inherit = "infrastructure.database"

    contract_id = fields.Many2one(
        'sale.subscription',
        string='Contract',
        domain="[('partner_id','child_of',partner_id),('state','=','open')]",
    )
    contract_state = fields.Selection(
        related='contract_id.state',
        string='Contact Status',
        readonly=True,
    )

    @api.one
    def update_contract_data_from_database(self):
        client = self.get_client()
        localdict = {'client': client}
        for line in self.contract_id.recurring_invoice_line_ids:
            expression = line.product_id.contracted_quantity_expression
            if not expression:
                continue
            localdict['recurring_line'] = line
            eval(
                expression,
                localdict,
                mode="exec",
                nocopy=True)
            result = localdict.get('result', False)
            if result:
                line.db_quantity = result

    @api.one
    def run_installation_command_on_remote_database(self):
        client = self.get_client()
        localdict = {'client': client}
        for line in self.contract_id.recurring_invoice_line_ids:
            expression = line.product_id.installation_command
            if not expression:
                continue
            localdict['recurring_line'] = line
            eval(
                expression,
                localdict,
                mode="exec",
                nocopy=True)
            result = localdict.get('result', False)
            if result:
                self.message_post(
                    subject=_('Installation response'),
                    body=result)

    @api.one
    def create_db(self):
        res = super(database, self).create_db()
        self.run_installation_command_on_remote_database()
        return res

    @api.one
    def update_remote_contracted_products(self):
        client = self.get_client()
        modules = ['adhoc_modules']
        for module in modules:
            if client.modules(name=module, installed=True) is None:
                raise ValidationError(_(
                    "You can not Upload a Contract if module '%s' is not "
                    "installed in the database") % (module))
        client.model('support.contract').remote_update_modules_data(True)

    @api.one
    def upload_contract_data(self):
        client = self.get_client()
        modules = ['web_support_client']
        for module in modules:
            if client.modules(name=module, installed=True) is None:
                raise ValidationError(_(
                    "You can not Upload a Contract if module '%s' is not "
                    "installed in the database") % (module))
        if not self.contract_id:
            raise ValidationError(
                _("You can not Upload a Contract if not contracted is linked"))
        imp_fields = [
            'id',
            'name',
            'user',
            'database',
            'server_host',
            'contract_id']
        ['self.asd', ]
        commercial_partner = self.contract_id.partner_id.commercial_partner_id

        server_host = self.env['ir.config_parameter'].get_param('web.base.url')

        # search for user related to commercial partner
        user = self.env['res.users'].search([(
            'partner_id', '=', commercial_partner.id)], limit=1)
        if not user:
            user = user.search([(
                'partner_id', 'child_of', commercial_partner.id)], limit=1)
        if not user:
            raise ValidationError(_(
                "You can not Upload a Contract if there is not user related "
                "to the contract Partner"))
        rows = [[
            'infrastructure_contract.contract_id_%i' % self.contract_id.id,
            self.contract_id.name,
            user.login,
            self._cr.dbname,
            server_host,
            self.contract_id.analytic_account_id.id,
        ]]
        client.model('support.contract').load(imp_fields, rows)
