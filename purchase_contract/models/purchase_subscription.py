# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################

from dateutil.relativedelta import relativedelta
import datetime
import logging
import time
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
from openerp.addons.decimal_precision import decimal_precision as dp

_logger = logging.getLogger(__name__)


class PurchaseSubscription(models.Model):
    _name = "purchase.subscription"
    _description = "Purchase Subscription"
    _inherits = {'account.analytic.account': 'analytic_account_id'}
    _inherit = 'mail.thread'

    @api.multi
    @api.depends('recurring_invoice_line_ids')
    def _get_recurring_price(self):
        for account in self:
            account.recurring_total = sum(
                line.price_subtotal for line in account.
                recurring_invoice_line_ids)

    recurring_invoice_line_ids = fields.One2many(
        'purchase.subscription.line',
        'analytic_account_id', 'Invoice Lines', copy=True)
    recurring_total = fields.Float(
        compute='_get_recurring_price',
        string="Recurring Price",
        store=True, track_visibility='onchange')
    template_id = fields.Many2one(
        'purchase.subscription',
        'Subscription Template',
        domain=[('type', '=', 'template')],
        track_visibility='onchange')
    state = fields.Selection(
        [('draft', 'New'),
         ('open', 'In Progress'),
         ('pending', 'To Renew'),
         ('close', 'Closed'),
         ('cancel', 'Cancelled')],
        'Status',
        required=True,
        track_visibility='onchange', copy=False, default='draft')
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        'Analytic Account', required=True, ondelete="cascade", auto_join=True)
    date_start = fields.Date('Start Date', default=time.strftime('%Y-%m-%d'))
    date = fields.Date('End Date', track_visibility='onchange')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency', required=True)
    recurring_rule_type = fields.Selection(
        [('daily', 'Day(s)'),
         ('weekly', 'Week(s)'),
         ('monthly', 'Month(s)'), (
            'yearly', 'Year(s)'), ],
        'Recurrency',
        help="Invoice automatically repeat at specified interval",
        default='monthly')
    recurring_interval = fields.Integer(
        'Repeat Every',
        help="Repeat every (Days/Week/Month/Year)", default=1)
    recurring_next_date = fields.Date(
        'Date of Next Invoice')
    close_reason_id = fields.Many2one(
        "purchase.subscription.close.reason",
        "Close Reason", track_visibility='onchange')
    type = fields.Selection(
        [('contract', 'Contract'),
         ('template', 'Template')], 'Type',
        default='contract')
    description = fields.Text('Description')
    user_id = fields.Many2one(
        'res.users', 'Responsible', track_visibility='onchange')
    manager_id = fields.Many2one(
        'res.users', 'Purchase Rep', track_visibility='onchange')

    _defaults = {
        'name': 'New',
        'code': lambda s, c, u, ctx: s.pool['ir.sequence'].next_by_code(
            c, u, 'purchase.subscription', context=ctx) or 'New',
    }

    @api.multi
    def set_open(self):
        return self.write({'state': 'open', 'date': False})

    @api.multi
    def set_pending(self):
        return self.write({'state': 'pending'})

    @api.multi
    def set_cancel(self):
        return self.write({'state': 'cancel'})

    @api.multi
    def set_close(self):
        return self.write({'state': 'close', 'date': datetime.date.today(
        ).strftime(DEFAULT_SERVER_DATE_FORMAT)})

    @api.multi
    def recurring_invoice(self):
        return self._recurring_create_invoice()

    @api.model
    def create(self, vals):
        if not vals.get('code', False):
            vals['code'] = self.env['ir.sequence'].next_by_code(
                'purchase.subscription') or 'New'
        if vals.get('name', 'New') == 'New':
            vals['name'] = vals['code']
        return super(PurchaseSubscription, self).create(vals)

    @api.multi
    def _prepare_invoice_data(self):
        journal_obj = self.env['account.journal']
        invoice = {}
        if not self.partner_id:
            raise ValidationError(_(
                "No Supplier Defined!\n"
                "You must first select a Supplier for "
                "Contract %s!") % self.name)

        fpos = self.partner_id.property_account_position_id or False
        journal_ids = journal_obj.search([(
            'type', '=', 'purchase'), ('company_id', '=', self.
                                       company_id.id)], limit=1)
        if not journal_ids:
            raise ValidationError(_(
                'Please define a pruchase journal for the company "%s".') % (
                self.company_id.name or '', ))

        currency_id = False
        if self.currency_id:
            currency_id = self.currency_id.id
        elif self.partner_id.property_product_pricelist:
            currency_id = self.partner_id.\
                property_product_pricelist.currency_id.id
        elif self.company_id:
            currency_id = self.company_id.currency_id.id

        invoice = {
            'account_id': self.partner_id.property_account_payable_id.id,
            'type': 'in_invoice',
            'reference': self.name,
            'partner_id': self.partner_id.id,
            'currency_id': currency_id,
            'journal_id': len(journal_ids) and journal_ids[0].id or False,
            'date_invoice': self.recurring_next_date,
            'origin': self.code,
            'fiscal_position_id': fpos and fpos.id,
            'company_id': self.company_id.id,
        }
        return invoice

    @api.model
    def _prepare_invoice_lines(self, fiscal_position_id):

        fiscal_position = self.env['account.fiscal.position'].browse(
            fiscal_position_id)

        invoice_lines = []
        for line in self.recurring_invoice_line_ids:

            res = line.product_id
            account_id = res.property_account_expense_id.id
            if not account_id:
                account_id = res.categ_id.property_account_expense_categ_id.id
            account_id = fiscal_position.map_account(account_id)

            taxes = res.supplier_taxes_id.filtered(
                lambda r: r.company_id == line.
                analytic_account_id.company_id)

            taxes = fiscal_position.map_tax(taxes)

            invoice_lines.append((0, 0, {
                'name': line.name,
                'account_id': account_id,
                'account_analytic_id': (
                    line.analytic_account_id.analytic_account_id.id),
                'price_unit': line.price_unit or 0.0,
                'quantity': line.quantity,
                'uom_id': line.uom_id.id or False,
                'product_id': line.product_id.id or False,
                'invoice_line_tax_ids': [(6, 0, taxes.ids)],
            }))
        return invoice_lines

    @api.model
    def _cron_recurring_create_invoice_purchase(self):
        current_date = time.strftime('%Y-%m-%d')
        contract_ids = self.search(
            [('recurring_next_date', '<=', current_date), (
                'state', '=', 'open')])
        return contract_ids._recurring_create_invoice()

    @api.multi
    def _prepare_invoice(self):
        invoice = self._prepare_invoice_data()
        invoice['invoice_line_ids'] = self._prepare_invoice_lines(
            invoice['fiscal_position_id'])
        return invoice

    @api.multi
    def _recurring_create_invoice(self, automatic=False):
        invoice_ids = []
        current_date = time.strftime('%Y-%m-%d')
        ids = [c.id for c in self]
        if ids:
            contract_ids = ids
        else:
            contract_ids = self.search([(
                'recurring_next_date', '<=', current_date),
                ('state', '=', 'open'), ('type', '=', 'contract')])

        if contract_ids:
            self.env.cr.execute(
                'SELECT a.company_id, array_agg(psub.id) as ids '
                'FROM purchase_subscription as psub JOIN'
                ' account_analytic_account as a'
                ' ON psub.analytic_account_id = a.id '
                'WHERE psub.id IN %s GROUP BY a.company_id',
                (tuple(contract_ids),))
            for company_id, ids in self._cr.fetchall():
                context_company = dict(
                    company_id=company_id, force_company=company_id)
                for contract in self.with_context(context_company):
                    try:
                        invoice_values = contract._prepare_invoice()
                        invoice_ids.append(self.env['account.invoice'].create(
                            invoice_values))
                        invoice_ids[-1].compute_taxes()
                        next_date = datetime.datetime.strptime(
                            contract.recurring_next_date or current_date,
                            "%Y-%m-%d")
                        interval = contract.recurring_interval
                        if contract.recurring_rule_type == 'daily':
                            new_date = next_date + \
                                relativedelta(days=+interval)
                        elif contract.recurring_rule_type == 'weekly':
                            new_date = next_date + \
                                relativedelta(weeks=+interval)
                        elif contract.recurring_rule_type == 'monthly':
                            new_date = next_date + \
                                relativedelta(months=+interval)
                        else:
                            new_date = next_date + \
                                relativedelta(years=+interval)
                        contract.write({
                            'recurring_next_date': new_date.
                            strftime('%Y-%m-%d')})
                        if automatic:
                            self._cr.commit()
                    except Exception:
                        if automatic:
                            self._cr.rollback()
                            _logger.exception(
                                'Fail to create recurring invoice '
                                'for contract %s', contract.code)
                        else:
                            raise
        return invoice_ids

    @api.onchange('partner_id')
    def on_change_partner(self):
        currency_id = self.\
            partner_id.property_purchase_currency_id.id or self.\
            env.user.company_id.currency_id.id
        self.currency_id = currency_id

    @api.multi
    def name_get(self):
        res = []
        for sub in self:
            if sub.type != 'template':
                name = '%s - %s' % (
                    sub.code,
                    sub.partner_id.name) if sub.code else sub.partner_id.name
                res.append((sub.id, '%s/%s' % (
                    sub.template_id.code,
                    name) if sub.template_id.code else name))
            else:
                name = '%s - %s' % (
                    sub.code,
                    sub.name) if sub.code else sub.name
                res.append((sub.id, name))
        return res

    @api.onchange('template_id')
    def on_change_template(self):
        if self.template_id.currency_id:
            self.currency_id = self.template_id.currency_id.id
        if self.template_id.description:
            self.description = self.template_id.description
        if self.template_id:
            self.recurring_interval = self.template_id.recurring_interval
            self.recurring_rule_type = self.template_id.recurring_rule_type
        invoice_line_ids = []
        for x in self.template_id.recurring_invoice_line_ids:
            invoice_line_ids.append((0, 0, {
                'product_id': x.product_id.id,
                'uom_id': x.uom_id.id,
                'name': x.name,
                'quantity': x.quantity,
                'price_unit': x.price_unit,
                'analytic_account_id': x.
                analytic_account_id and x.
                analytic_account_id.id or False,
            }))
        self.recurring_invoice_line_ids = invoice_line_ids

    @api.multi
    def action_subscription_invoice(self):
        analytic_ids = [sub.analytic_account_id.id for sub in self]
        invoice_ids = self.env['account.invoice'].search(
            [('invoice_line_ids.account_analytic_id', 'in', analytic_ids),
             ('origin', 'in', [sub.code for sub in self])])
        imd = self.env['ir.model.data']
        list_view_id = imd.xmlid_to_res_id('account.invoice_supplier_tree')
        form_view_id = imd.xmlid_to_res_id('account.invoice_supplier_form')
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.invoice",
            "views": [[list_view_id, "tree"], [form_view_id, "form"]],
            "domain": [["id", "in", invoice_ids.ids]],
            "context": {"create": False},
        }

    @api.model
    def cron_account_analytic_account(self):
        remind = {}

        def fill_remind(key, domain, write_pending=False):
            base_domain = [
                ('type', '=', 'contract'),
                ('partner_id', '!=', False),
                ('manager_id', '!=', False),
                ('manager_id.email', '!=', False),
            ]
            base_domain.extend(domain)
            accounts = self.search(base_domain, order='name asc')
            for account in accounts:
                if write_pending:
                    account.write({'state': 'pending'})
                remind_user = remind.setdefault(account.manager_id.id, {})
                remind_type = remind_user.setdefault(key, {})
                remind_type.setdefault(
                    account.partner_id, []).append(account)

        # Already expired
        fill_remind("old", [('state', 'in', ['pending'])])

        # Expires now
        fill_remind("new", [('state', 'in', ['draft', 'open']),
                            '&', ('date', '!=', False),
                            ('date', '<=', time.strftime('%Y-%m-%d')),
                            ], True)

        # Expires in less than 30 days
        fill_remind("future", [
            ('state', 'in', ['draft', 'open']),
            ('date', '!=', False),
            ('date', '<', (datetime.datetime.now() + datetime
                           .timedelta(30)).strftime("%Y-%m-%d"))])
        base_url = self.env['ir.config_parameter'].get_param(
            'web.base.url')
        action_id = self.env['ir.model.data'].get_object_reference(
            'purchase_contract', 'purchase_subscription_action')[1]
        template_id = self.env['ir.model.data'].get_object_reference(
            'purchase_contract',
            'purchase_account_analytic_cron_email_template')[1]
        for user_id, data in remind.items():
            _logger.debug("Sending reminder to uid %s", user_id)
            self.env['mail.template'].browse(template_id).with_context(
                base_url=base_url, action_id=action_id, data=data).send_mail(
                user_id, force_send=True)
        return True


class PurchaseSubscriptionLine(models.Model):
    _name = "purchase.subscription.line"
    _description = "Purchase Subscription Line"

    @api.multi
    def _amount_line(self):
        for line in self:
            price = line.product_id.taxes_id.\
                _fix_tax_included_price(
                    line.price_unit, line.product_id.taxes_id, [])
            line.price_subtotal = line.\
                quantity * price * (100.0 - line.discount) / 100.0
            if line.analytic_account_id.currency_id:
                line.price_subtotal = line.analytic_account_id\
                    .currency_id.round(line.price_subtotal)

    analytic_account_id = fields.Many2one(
        'purchase.subscription', 'Subscription', ondelete='cascade')
    quantity = fields.Float('Quantity', compute='_compute_quantity')
    purchase_quantity = fields.Float('Purchase Quantity')
    product_id = fields.Many2one(
        'product.product', string='Product', required=True)
    name = fields.Text('Description', required=True)
    uom_id = fields.Many2one('product.uom', 'Unit of Measure', required=True)
    price_unit = fields.Float('Unit Price', required=True)
    discount = fields.Float(
        'Discount (%)', digits=dp.get_precision('Discount'))
    price_subtotal = fields.Float(
        compute=_amount_line,
        string='Sub Total', digits=dp.get_precision('Account'))

    @api.multi
    @api.depends('purchase_quantity')
    def _compute_quantity(self):
        for rec in self:
            rec.quantity = rec.purchase_quantity

    @api.onchange('product_id')
    def product_id_change(self):
        product = self.product_id.with_context({
            'lang': self.analytic_account_id.partner_id.lang,
            'partner_id': self.analytic_account_id.partner_id.id,
        })
        name = product.display_name
        if product.name:
            name = product.name_get()[0][1]
            if product.description_purchase:
                name += '\n' + product.description_purchase

        self.name = name
        self.uom_id = self.uom_id.id or product.uom_id.id or False
        self.price_unit = product.list_price
        seller = self.product_id._select_seller(
            self.product_id,
            partner_id=self.analytic_account_id.partner_id,
            quantity=self.quantity,
            uom_id=self.uom_id)

        if seller:
            self.price_unit = seller.price
            if self.price_unit and seller and self.analytic_account_id.\
                    currency_id and seller.currency_id != self.\
                    analytic_account_id.currency_id:
                self.price_unit = seller.currency_id.compute(
                    self.price_unit, self.analytic_account_id.currency_id)

            if seller and self.uom_id and seller.product_uom != self.uom_id:
                self.price_unit = self.env['product.uom']._compute_price(
                    seller.product_uom.id, self.price_unit, self.uom_id.id)

        if self.uom_id.id != product.uom_id.id:
            self.price_unit = self.env['product.uom']._compute_price(
                product.uom_id.id,
                self.price_unit, self.uom_id.id)
        if self.uom_id:
            return {'domain': {'uom_id': [
                ('category_id', '=', product.uom_id.category_id.id)]}}
        else:
            return {'domain': {'uom_id': []}}

    @api.onchange('uom_id')
    def product_uom_change(self):
        if not self.uom_id:
            self.price_unit = 0.0
            self.uom_id = self.uom_id or False
        return self.product_id_change()


class PurchaseSubscriptionCloseReason(models.Model):
    _name = "purchase.subscription.close.reason"
    _order = "sequence, id"

    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence', default=10)


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    purchase_subscription_ids = fields.One2many(
        'purchase.subscription',
        'analytic_account_id', 'Purchase Subscriptions')
