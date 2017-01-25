# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenUpgrade module for Odoo
#    @copyright 2015-Today: Odoo Community Association
#    @author: Stephane LE CORNEC
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openupgradelib import openupgrade


@openupgrade.migrate(use_env=True)
def migrate(env, version):
    create_purchase_subscriptions(env)


def create_purchase_subscriptions(env):
    cr = env.cr
    # we only migrate purchase contracts, not templates
    openupgrade.logged_query(cr, """
        SELECT
            id,
            name,
            partner_id,
            manager_id,
            code,
            date_start,
            date,
            recurring_next_date,
            recurring_rule_type,
            recurring_interval,
            state,
            user_id,
            company_id,
            description
        FROM account_analytic_account
        WHERE type = 'purchase_contract' and state != 'template'
        """)
    for contract_data in cr.fetchall():
        (
            contract_id,
            name,
            partner_id,
            manager_id,
            code,
            date_start,
            date,
            recurring_next_date,
            recurring_rule_type,
            recurring_interval,
            state,
            user_id,
            company_id,
            description) = contract_data
        contract_line_vals = []
        # TODO search for this table somewhere (or copy this into another)
        if openupgrade.table_exists(cr, 'account_analytic_invoice_line_copy'):
            openupgrade.logged_query(cr, """
                SELECT
                    name,
                    quantity,
                    product_id,
                    price_unit,
                    uom_id
                FROM account_analytic_invoice_line_copy
                WHERE analytic_account_id = %s
                """, (contract_id,))
            for contract_line_data in cr.fetchall():
                (
                    line_name,
                    line_purchase_quantity,
                    line_product_id,
                    line_price_unit,
                    line_uom_id) = contract_line_data
                contract_line_vals.append((0, False, {
                    'name': line_name,
                    'purchase_quantity': line_purchase_quantity,
                    'product_id': line_product_id,
                    'price_unit': line_price_unit,
                    'uom_id': line_uom_id,
                }))

        contract_vals = {
            'name': name,
            'partner_id': partner_id,
            'manager_id': manager_id,
            'code': code,
            'analytic_account_id': contract_id,
            'date_start': date_start,
            'date': date,
            'recurring_next_date': recurring_next_date,
            'recurring_rule_type': recurring_rule_type,
            'recurring_interval': recurring_interval,
            'state': state,
            'user_id': user_id,
            'company_id': company_id,
            'description': description,
            'type': 'contract',
            'recurring_invoice_line_ids': contract_line_vals,
        }
        env['purchase.subscription'].create(contract_vals)
