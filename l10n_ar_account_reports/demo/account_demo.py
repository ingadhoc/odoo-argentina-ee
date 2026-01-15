# pylint: disable=consider-merging-classes-inherited
import logging
import re

from dateutil.relativedelta import relativedelta
from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @api.model
    def _install_l10n_ar_account_reports_demo(self, companies):
        for company in companies:
            self = self.with_company(company)
            # seteamos multilateral a los fines de demo. si luego queremos manejar otros casos podemos hacer esto
            # SOLO sobre RI
            company.l10n_ar_gross_income_type = "multilateral"
            demo_data = {
                "account.fiscal.position": self._l10n_ar_get_demo_data_fiscal_position(),
                "account.move": self._l10n_ar_get_demo_data_move(),
            }
            # skip_readonly_check es solo para poder hacer pruebas de volver a cargar data
            self.sudo().with_context(skip_pdf_attachment_generation=True, skip_readonly_check=True)._load_data(
                demo_data
            )
            self._l10n_ar_post_load_demo_data()
            self._l10n_ar_create_payments()
            if not company.account_opening_date:
                company.account_opening_date = fields.Date.today() + relativedelta(months=-2, day=1)

    @api.model
    def _l10n_ar_create_payments(self):
        invoices = self._l10n_ar_demo_get_invoices()
        for invoice in invoices.filtered(
            lambda x: x.move_type == "in_invoice" and x.state == "posted" and x.amount_residual > 0.0
        ):
            action_context = invoice.action_register_payment()["context"]
            vals = {
                "amount": invoice.amount_residual,
                # queremos el pago en el mes pasado
                "date": invoice.invoice_date,
            }
            payment = self.env["account.payment"].with_context(**action_context).create(vals)
            payment.action_post()
        for invoice in invoices.filtered(
            lambda x: x.move_type == "out_invoice" and x.state == "posted" and x.amount_residual > 0.0
        ):
            action_context = invoice.action_register_payment()["context"]
            withholding_amount = 1000.50
            # para jugar con distintos casos usamos la provincia del cliente y suponemos que nos retiene de la misma jurisdicción
            tax = self.env["account.tax"].search(
                [
                    ("company_id", "=", invoice.company_id.id),
                    ("l10n_ar_state_id", "!=", invoice.partner_id.state_id.id),
                    ("l10n_ar_state_id.country_id.code", "=", "AR"),
                    ("l10n_ar_withholding_payment_type", "=", "customer"),
                ],
                limit=1,
            )

            if tax:
                l10n_ar_withholding_line_ids = [
                    Command.create(
                        {
                            "name": "0001-00000001",
                            "tax_id": tax.id,
                            "amount": withholding_amount,
                        }
                    )
                ]
            else:
                l10n_ar_withholding_line_ids = []

            # para este partner creamos tmb retención de IVA
            if invoice.partner_id.id == self.env.ref("l10n_ar_account_reports.res_partner_adhoc_pba").id:
                l10n_ar_withholding_line_ids.append(
                    Command.create(
                        {
                            "name": "0001-00000002",
                            "tax_id": self.ref("ri_tax_withholding_vat_incurred").id,
                            "amount": 10000.0,
                        }
                    )
                )
            vals = {
                "amount": invoice.amount_residual - withholding_amount if tax else invoice.amount_residual,
                # queremos el pago en el mes pasado
                "date": invoice.invoice_date,
                "l10n_ar_withholding_line_ids": l10n_ar_withholding_line_ids,
            }
            payment = self.env["account.payment"].with_context(**action_context).create(vals)
            payment.action_post()

    @api.model
    def _l10n_ar_get_tax(self, xmlid, rate):
        # TODO cuando pasemos a usar tax groups podemos usar el ensure_tax de "account.fiscal.position.l10n_ar_tax""
        tax = self.ref(xmlid)
        if "%" not in tax.name:
            name = f"{tax.name} {rate}%"
        else:
            # Usamos re.sub para reemplazar el patrón con el nuevo número seguido de '%'
            # Si ya tiene un porcentaje, lo reemplazamos
            name = re.sub(r"\b\d+(\.\d+)?\s*%", f"{rate}%", tax.name)

        new_tax = tax.search(
            [("name", "=", name), ("company_id", "=", self.env.company.id), ("type_tax_use", "=", tax.type_tax_use)],
            limit=1,
        )
        if not new_tax:
            new_tax = tax.copy(
                default={
                    # dejamos sequencia mas baja para que siempre el que se duplica sea el que esta arriba
                    "sequence": 10,
                    "amount": rate,
                    "active": True,
                    "name": name,
                }
            )
        return new_tax

    @api.model
    def _l10n_ar_get_demo_data_fiscal_position(self):
        # Función auxiliar para generar la estructura repetitiva
        def _get_vals(name, state_xml_id, tax_type, tax_rec, sequence):
            return {
                "name": name,
                "sequence": sequence,
                "auto_apply": True,
                "country_id": "base.ar",
                "state_ids": [Command.set([state_xml_id])],
                "l10n_ar_afip_responsibility_type_ids": [Command.set(["l10n_ar.res_IVARI"])],
                "l10n_ar_tax_ids": [
                    Command.clear(),
                    Command.create({"tax_type": tax_type, "default_tax_id": tax_rec.id}),
                ],
            }

        # Obtención de impuestos (nombres de variables acortados para legibilidad)
        pba_perc = self._l10n_ar_get_tax("ri_tax_percepcion_iibb_ba_aplicada", 3)
        mis_perc = self._l10n_ar_get_tax("ri_tax_percepcion_iibb_mi_aplicada", 3)
        sf_perc = self._l10n_ar_get_tax("ri_tax_percepcion_iibb_sf_aplicada", 3)
        tuc_perc = self._l10n_ar_get_tax("ri_tax_percepcion_iibb_tn_aplicada", 3)

        pba_ret = self._l10n_ar_get_tax("ex_tax_withholding_iibb_ba_applied", 3)
        mis_ret = self._l10n_ar_get_tax("ex_tax_withholding_iibb_ms_applied", 3)
        sf_ret = self._l10n_ar_get_tax("ex_tax_withholding_iibb_sf_applied", 3)
        tuc_ret = self._l10n_ar_get_tax("ex_tax_withholding_iibb_t_applied", 3)
        mza_ret = self._l10n_ar_get_tax("ex_tax_withholding_iibb_mza_applied", 3)

        return {
            "demo_fp_perc_pba": _get_vals(
                "Percepciones P. Buenos Aires", "base.state_ar_b", "perception", pba_perc, 15
            ),
            "demo_fp_perc_misiones": _get_vals("Percepciones Misiones", "base.state_ar_n", "perception", mis_perc, 15),
            "demo_fp_perc_santa_fe": _get_vals("Percepciones Santa Fe", "base.state_ar_s", "perception", sf_perc, 15),
            "demo_fp_perc_tucuman": _get_vals("Percepciones Tucumán", "base.state_ar_t", "perception", tuc_perc, 15),
            "demo_fp_ret_pba": _get_vals("Retenciones P. Buenos Aires", "base.state_ar_b", "withholding", pba_ret, 60),
            "demo_fp_ret_misiones": _get_vals("Retenciones Misiones", "base.state_ar_n", "withholding", mis_ret, 60),
            "demo_fp_ret_santa_fe": _get_vals("Retenciones Santa Fe", "base.state_ar_s", "withholding", sf_ret, 60),
            "demo_fp_ret_tucuman": _get_vals("Retenciones Tucumán", "base.state_ar_t", "withholding", tuc_ret, 60),
            "demo_fp_ret_mendoza": _get_vals("Retenciones Mendoza", "base.state_ar_m", "withholding", mza_ret, 60),
        }

    @api.model
    def _l10n_ar_get_demo_data_move(self):
        result = {}
        one_month_ago = fields.Date.today() + relativedelta(months=-1, day=1)
        two_month_ago = fields.Date.today() + relativedelta(months=-2, day=1)
        result["demo_invoice_two_months"] = {
            "move_type": "out_invoice",
            "partner_id": "l10n_ar_account_reports.res_partner_adhoc_pba",
            "invoice_date": two_month_ago,
            "invoice_line_ids": [
                Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 300000.0})
            ],
        }
        result["demo_sup_invoice_customer_two_months"] = {
            "move_type": "in_invoice",
            "partner_id": "l10n_ar.res_partner_mipyme",
            "invoice_date": two_month_ago,
            "l10n_latam_document_number": "12-0001",
            "invoice_line_ids": [
                Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 330000.0})
            ],
        }
        provinces = ["mendoza", "misiones", "caba", "pba", "cordoba", "santa_fe", "tucuman"]
        for idx, province in enumerate(provinces, start=1):
            module = "l10n_ar_tax" if province in ["caba", "cordoba"] else "l10n_ar_account_reports"

            # create customer invoice
            # usamos precio unitario más grande que en compras para que quede IVA a pagar
            result[f"demo_invoice_{province}"] = {
                "move_type": "out_invoice",
                "partner_id": f"{module}.res_partner_adhoc_{province}",
                "invoice_date": one_month_ago,
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 600000.0})
                ],
            }

            # create supplier invoice
            result[f"demo_sup_invoice_{province}"] = {
                "move_type": "in_invoice",
                "partner_id": f"{module}.res_partner_adhoc_{province}",
                "invoice_date": one_month_ago,
                "l10n_latam_document_number": f"1-100{idx}",
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 300000.0})
                ],
            }
        # despacho
        result["demo_sup_invoice_suffered_1"] = {
            "move_type": "in_invoice",
            "partner_id": "l10n_ar.res_partner_mipyme",
            "invoice_date": one_month_ago,
            "l10n_latam_document_number": "12-1234",
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": "product.product_product_2",
                        "quantity": 1,
                        "price_unit": 300000.0,
                        "tax_ids": [
                            Command.set(
                                [
                                    "ri_tax_percepcion_iva_sufrida",
                                    "ri_tax_vat_21_compras",
                                    "ri_tax_percepcion_iibb_ba_sufrida",
                                    "ri_tax_percepcion_iibb_caba_sufrida",
                                    "ri_tax_percepcion_iibb_ca_sufrida",
                                    "ri_tax_percepcion_iibb_co_sufrida",
                                    "ri_tax_percepcion_iibb_rr_sufrida",
                                    "ri_tax_percepcion_iibb_er_sufrida",
                                ]
                            )
                        ],
                    }
                ),
            ],
        }
        # factura con percepciones
        result["demo_sup_invoice_suffered_2"] = {
            "move_type": "in_invoice",
            "partner_id": "l10n_ar.partner_afip",
            "invoice_date": one_month_ago,
            "l10n_latam_document_number": "1234567890123456",
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": "product.product_product_2",
                        "quantity": 1,
                        "price_unit": 300000.0,
                        "tax_ids": [
                            Command.set(
                                [
                                    "ri_tax_percepcion_iva_sufrida",
                                    "ri_tax_vat_21_compras",
                                    "ri_tax_percepcion_iibb_ba_sufrida",
                                    "ri_tax_percepcion_iibb_caba_sufrida",
                                    "ri_tax_percepcion_iibb_ca_sufrida",
                                    "ri_tax_percepcion_iibb_co_sufrida",
                                    "ri_tax_percepcion_iibb_rr_sufrida",
                                    "ri_tax_percepcion_iibb_er_sufrida",
                                ]
                            )
                        ],
                    }
                ),
            ],
        }
        return result

    @api.model
    def _l10n_ar_demo_get_invoices(self):
        invoices = self.env["account.move"]
        for xmlid in self._l10n_ar_get_demo_data_move().keys():
            invoices |= self.ref(xmlid)
        return invoices

    @api.model
    def _l10n_ar_post_load_demo_data(self):
        invoices = self._l10n_ar_demo_get_invoices()
        invoices.filtered(lambda m: m.state == "draft").action_post()
