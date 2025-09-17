# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import namedtuple

from odoo import _, models
from odoo.exceptions import RedirectWarning
from odoo.http import request
from odoo.tools.float_utils import float_round


class ArgentinianReportCustomHandler(models.AbstractModel):
    _inherit = "l10n_ar.tax.report.handler"

    def _check_invoices(self, invoices):
        l10n_ar_vat_afip_code = {"0": 0, "1": 0, "2": 0, "3": 0, "4": 10.5, "5": 21, "6": 27, "8": 5, "9": 2.5}

        InvoiceDiff = namedtuple(
            "InvoiceDiff",
            [
                "invoice_id",  # inv.id
                "invoice_date",  # inv.date
                "partner_name",  # inv.partner_id.name
                "invoice_name",  # inv.name
                "vat_rate",  # l10n_ar_vat_afip_code[vat_tax['Id']]
                "base_and_importe",  # (vat_tax['BaseImp'], vat_tax['Importe'])
                "calculated_amount",  # calculated_amount
                "difference",  # diff
            ],
        )

        res = []
        for inv in invoices:
            vat_taxes = inv._get_vat()
            for vat_tax in vat_taxes:
                calculated_amount = vat_tax["BaseImp"] * l10n_ar_vat_afip_code[vat_tax["Id"]] / 100
                diff = float_round(abs(vat_tax["Importe"] - calculated_amount), precision_digits=2)
                if diff > 0.5:
                    res.append(
                        InvoiceDiff(
                            invoice_id=inv.id,
                            invoice_date=inv.date,
                            partner_name=inv.partner_id.name,
                            invoice_name=inv.name,
                            vat_rate=l10n_ar_vat_afip_code[vat_tax["Id"]],
                            base_and_importe=(vat_tax["BaseImp"], vat_tax["Importe"]),
                            calculated_amount=calculated_amount,
                            difference=diff,
                        )
                    )
        return res

    def _vat_book_get_REGINFO_CV_ALICUOTAS(self, options, tax_type, invoices):
        error = self._check_invoices(invoices)

        # Download the file only id: 1) if there not error, 2) We a are saas support user with active dev mode
        if not error or (self.env.user.has_group("saas_client.group_saas_support") and request.session.debug):
            return super()._vat_book_get_REGINFO_CV_ALICUOTAS(options, tax_type, invoices)

        invoices_domain = [("id", "in", [inv.invoice_id for inv in error])]
        raise RedirectWarning(
            _(
                "Existen comprobantes con diferencias mayores a 0.5 centavos en el cálculo de IVA."
                " ARCA no permitirá importar el archivo TXT hasta que se corrijan estos errores."
                " Para más información, visite la siguiente documentación: https://www.adhoc.inc/knowledge/article/9963"
            ),
            {
                "type": "ir.actions.act_window",
                "name": "Facturas con diferencias",
                "res_model": "account.move",
                "view_mode": "list",
                "views": [(False, "list"), (False, "form")],
                "domain": invoices_domain,
            },
            _("Corregir comprobantes"),
        )
