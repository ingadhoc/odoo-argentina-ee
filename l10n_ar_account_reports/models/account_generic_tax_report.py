# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class generic_tax_report(models.AbstractModel):
    _inherit = 'account.generic.tax.report'

    def _get_lines_by_tax(self, options, line_id, taxes):
        lines = []
        # INICIO CAMBIO
        # types = ['sale', 'purchase']
        types = ['sale', 'purchase', 'customer', 'supplier']
        # FIN CAMBIO
        groups = dict((tp, {}) for tp in types)
        for key, tax in taxes.items():

            # 'none' taxes are skipped.
            if tax['obj'].type_tax_use == 'none':
                continue

            if tax['obj'].amount_type == 'group':

                # Group of taxes without child are skipped.
                if not tax['obj'].children_tax_ids:
                    continue

                # - If at least one children is 'none', show the group of taxes.
                # - If all children are different of 'none', only show the children.

                tax['children'] = []
                tax['show'] = False
                for child in tax['obj'].children_tax_ids:

                    if child.type_tax_use != 'none':
                        continue

                    tax['show'] = True
                    for i, period_vals in enumerate(taxes[child.id]['periods']):
                        tax['periods'][i]['tax'] += period_vals['tax']

            groups[tax['obj'].type_tax_use][key] = tax

        period_number = len(options['comparison'].get('periods'))
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

                    if tax['obj'].amount_type == 'group':
                        report_line_name = tax['obj'].name
                    else:
                        report_line_name = '%s (%s)' % (tax['obj'].name, tax['obj'].amount)

                    lines.append({
                        'id': tax['obj'].id,
                        'name': report_line_name,
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
