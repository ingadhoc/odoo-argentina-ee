# pylint: disable=consider-merging-classes-inherited
import logging
import re

from dateutil.relativedelta import relativedelta
from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @api.model
    def _install_l10n_ar_account_reports_demo(self):
        # por ahora lo hacemos solo para RI, si luego queremos usar lógica de que pueda aplicar a cualquier compañía
        # deberiamos hacer parecido a _install_demo
        companies = self.env.ref("base.company_ri")
        for company in companies:
            self = self.with_company(company)
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
        # import pdb; pdb.set_trace()

    def _l10n_ar_create_payments(self):
        # def _l10n_ar_get_demo_data_payment(self):
        # mendoza_invoice = self.ref("demo_sup_invoice_mendoza")
        invoices = (
            self.ref("demo_sup_invoice_mendoza")
            + self.ref("demo_sup_invoice_mendoza")
            + self.ref("demo_sup_invoice_misiones")
            + self.ref("demo_sup_invoice_santa_fe")
            + self.ref("demo_sup_invoice_caba")
            + self.ref("demo_sup_invoice_pba")
        )
        # mendoza_invoice.action_register_payment(
        for invoice in invoices.filtered("amount_residual"):
            action_context = invoice.action_register_payment()["context"]
            vals = {
                # "journal_id": self.company_bank_journal.id,
                "amount": invoice.amount_residual,
                # "date": self.today,
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
        santafe_perc = self._l10n_ar_get_tax("ri_tax_percepcion_iibb_sf_aplicada", 3)
        misiones_perc = self._l10n_ar_get_tax("ri_tax_percepcion_iibb_mi_aplicada", 3)
        misiones_ret = self._l10n_ar_get_tax("ex_tax_withholding_iibb_ms_applied", 3)
        santafe_ret = self._l10n_ar_get_tax("ex_tax_withholding_iibb_sf_applied", 3)
        mendoza_ret = self._l10n_ar_get_tax("ex_tax_withholding_iibb_mza_applied", 3)
        return {
            "demo_fp_perc_misiones": {
                "name": "Percepciones Misiones",
                "sequence": 15,
                "auto_apply": True,
                "country_id": "base.ar",
                "state_ids": [Command.set(["base.state_ar_n"])],
                "l10n_ar_afip_responsibility_type_ids": [
                    Command.set(
                        [
                            "l10n_ar.res_IVARI",
                        ]
                    )
                ],
                "l10n_ar_tax_ids": [
                    Command.clear(),
                    Command.create({"tax_type": "perception", "default_tax_id": misiones_perc.id}),
                ],
            },
            "demo_fp_perc_santa_fe": {
                "name": "Percepciones Santa Fe",
                "sequence": 15,
                "auto_apply": True,
                "country_id": "base.ar",
                "state_ids": [
                    Command.set(
                        [
                            "base.state_ar_s",
                        ]
                    )
                ],
                "l10n_ar_afip_responsibility_type_ids": [
                    Command.set(
                        [
                            "l10n_ar.res_IVARI",
                        ]
                    )
                ],
                "l10n_ar_tax_ids": [
                    Command.clear(),
                    Command.create({"tax_type": "perception", "default_tax_id": santafe_perc.id}),
                ],
            },
            "demo_fp_ret_santa_fe": {
                "name": "Retenciones Santa Fe",
                "sequence": 60,
                "auto_apply": True,
                "country_id": "base.ar",
                "state_ids": [
                    Command.set(
                        [
                            "base.state_ar_s",
                        ]
                    )
                ],
                "l10n_ar_afip_responsibility_type_ids": [
                    Command.set(
                        [
                            "l10n_ar.res_IVARI",
                        ]
                    )
                ],
                "l10n_ar_tax_ids": [
                    Command.clear(),
                    Command.create({"tax_type": "withholding", "default_tax_id": santafe_ret.id}),
                ],
            },
            "demo_fp_ret_misiones": {
                "name": "Retenciones Misiones",
                "sequence": 60,
                "auto_apply": True,
                "country_id": "base.ar",
                "state_ids": [
                    Command.set(
                        [
                            "base.state_ar_n",
                        ]
                    )
                ],
                "l10n_ar_afip_responsibility_type_ids": [
                    Command.set(
                        [
                            "l10n_ar.res_IVARI",
                        ]
                    )
                ],
                "l10n_ar_tax_ids": [
                    Command.clear(),
                    Command.create({"tax_type": "withholding", "default_tax_id": misiones_ret.id}),
                ],
            },
            "demo_fp_ret_mendoza": {
                "name": "Retenciones Mendoza",
                "sequence": 60,
                "auto_apply": True,
                "country_id": "base.ar",
                "state_ids": [
                    Command.set(
                        [
                            "base.state_ar_m",
                        ]
                    )
                ],
                "l10n_ar_afip_responsibility_type_ids": [
                    Command.set(
                        [
                            "l10n_ar.res_IVARI",
                        ]
                    )
                ],
                "l10n_ar_tax_ids": [
                    Command.clear(),
                    Command.create({"tax_type": "withholding", "default_tax_id": mendoza_ret.id}),
                ],
            },
        }

    def _l10n_ar_get_demo_data_move(self):
        one_month_ago = fields.Date.today() + relativedelta(months=-1)
        return {
            "demo_invoice_mendoza": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_mendoza",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1}),
                ],
            },
            "demo_invoice_misiones": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_misiones",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1}),
                ],
            },
            "demo_invoice_caba": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_caba",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1}),
                ],
            },
            "demo_invoice_pba": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_pba",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1}),
                ],
            },
            "demo_invoice_cordoba": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_cordoba",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1}),
                ],
            },
            "demo_invoice_santa_fe": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_santa_fe",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1}),
                ],
            },
            "demo_sup_invoice_misiones": {
                "move_type": "in_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_misiones",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "l10n_latam_document_number": "0001-00001234",
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 100.0}),
                ],
            },
            "demo_sup_invoice_santa_fe": {
                "move_type": "in_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_santa_fe",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "l10n_latam_document_number": "0001-00001234",
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 100.0}),
                ],
            },
            "demo_sup_invoice_caba": {
                "move_type": "in_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_caba",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "l10n_latam_document_number": "0001-00001234",
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 100.0}),
                ],
            },
            "demo_sup_invoice_pba": {
                "move_type": "in_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_pba",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "l10n_latam_document_number": "0001-00001234",
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 100.0}),
                ],
            },
            "demo_sup_invoice_cordoba": {
                "move_type": "in_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_cordoba",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "l10n_latam_document_number": "0001-00001234",
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 100.0}),
                ],
            },
            "demo_sup_invoice_mendoza": {
                "move_type": "in_invoice",
                "partner_id": "l10n_ar_account_reports.res_partner_adhoc_mendoza",
                "invoice_date": one_month_ago.strftime("%Y-%m-01"),
                "l10n_latam_document_number": "0001-00001234",
                "invoice_line_ids": [
                    Command.create({"product_id": "product.product_product_2", "quantity": 1, "price_unit": 100.0}),
                ],
            },
        }

    def _l10n_ar_post_load_demo_data(self):
        invoices = (
            self.ref("demo_invoice_mendoza")
            + self.ref("demo_invoice_misiones")
            + self.ref("demo_invoice_caba")
            + self.ref("demo_invoice_pba")
            + self.ref("demo_invoice_cordoba")
            + self.ref("demo_sup_invoice_mendoza")
            + self.ref("demo_sup_invoice_misiones")
            + self.ref("demo_sup_invoice_santa_fe")
            + self.ref("demo_sup_invoice_caba")
            + self.ref("demo_sup_invoice_pba")
        )
        invoices.filtered(lambda m: m.state == "draft").action_post()
