# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api
from odoo.tools.translate import _
from odoo.tools.misc import formatLang


class generic_tax_report(models.AbstractModel):
    _inherit = 'account.generic.tax.report'

    @api.model
    def _get_lines(self, options, line_id=None):
        taxes = {}
        for tax in self.env['account.tax'].with_context(active_test=False).search([]):
            taxes[tax.id] = {'obj': tax, 'show': False, 'periods': [{'net': 0, 'tax': 0}]}
            for period in options['comparison'].get('periods'):
                taxes[tax.id]['periods'].append({'net': 0, 'tax': 0})
        period_number = 0
        self._compute_from_amls(options, taxes, period_number)
        for period in options['comparison'].get('periods'):
            period_number += 1
            self.with_context(date_from=period.get('date_from'), date_to=period.get('date_to'))._compute_from_amls(options, taxes, period_number)
        lines = []
        # INICIO CAMBIO
        # types = ['sale', 'purchase', 'adjustment']
        # FIN CAMBIO
        types = ['sale', 'purchase', 'customer', 'supplier', 'adjustment']
        groups = dict((tp, {}) for tp in types)
        for key, tax in taxes.items():
            if tax['obj'].type_tax_use == 'none':
                continue
            if tax['obj'].children_tax_ids:
                tax['children'] = []
                for child in tax['obj'].children_tax_ids:
                    if child.type_tax_use != 'none':
                        continue
                    tax['children'].append(taxes[child.id])
            if tax['obj'].children_tax_ids and not tax.get('children'):
                continue
            groups[tax['obj'].type_tax_use][key] = tax
        line_id = 0
        for tp in types:
            if not any([tax.get('show') for key, tax in groups[tp].items()]):
                continue
            sign = tp == 'sale' and -1 or 1
            lines.append({
                    'id': tp,
                    'name': self._get_type_tax_use_string(tp),
                    'unfoldable': False,
                    'columns': [{} for k in range(0, 2 * (period_number + 1) or 2)],
                    'level': 1,
                })
            for key, tax in sorted(groups[tp].items(), key=lambda k: k[1]['obj'].sequence):
                if tax['show']:
                    columns = []
                    for period in tax['periods']:
                        columns += [{'name': self.format_value(period['net'] * sign), 'style': 'white-space:nowrap;'},{'name': self.format_value(period['tax'] * sign), 'style': 'white-space:nowrap;'}]
                    lines.append({
                        'id': tax['obj'].id,
                        'name': tax['obj'].name + ' (' + str(tax['obj'].amount) + ')',
                        'unfoldable': False,
                        'columns': columns,
                        'level': 4,
                        'caret_options': 'account.tax',
                    })
                    for child in tax.get('children', []):
                        columns = []
                        for period in child['periods']:
                            columns += [{'name': self.format_value(period['net'] * sign), 'style': 'white-space:nowrap;'},{'name': self.format_value(period['tax'] * sign), 'style': 'white-space:nowrap;'}]
                        lines.append({
                            'id': child['obj'].id,
                            'name': '   ' + child['obj'].name + ' (' + str(child['obj'].amount) + ')',
                            'unfoldable': False,
                            'columns': columns,
                            'level': 4,
                            'caret_options': 'account.tax',
                        })
            line_id += 1
        return lines
