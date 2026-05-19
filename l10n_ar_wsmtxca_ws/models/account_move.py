from markupsafe import Markup
from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import plaintext2html
from odoo.tools.float_utils import float_repr, float_round


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ar_do_afip_ws_request_cae(self, client, auth, transport):
        """Override to handle wsmtxca webservice logic."""
        non_wsmtxca = self.filtered(lambda x: x.journal_id.l10n_ar_afip_ws != "wsmtxca")
        if non_wsmtxca:
            return_info = super(AccountMove, non_wsmtxca)._l10n_ar_do_afip_ws_request_cae(client, auth, transport)
            if return_info:
                return return_info

        for inv in self.filtered(lambda x: x.journal_id.l10n_ar_afip_ws == "wsmtxca" and not x.l10n_ar_afip_auth_code):
            afip_ws = inv.journal_id.l10n_ar_afip_ws
            errors = obs = events = ""
            return_codes = []
            values = {}

            inv.l10n_ar_check_rate()

            ws_method = "autorizarComprobante"
            request_data = inv.wsmtxca_get_cae_request(client)
            auth = inv.journal_id._wsmtxca_convert_auth(auth)
            self._ws_verify_request_data(client, auth, ws_method, request_data)

            response = client.service[ws_method](auth, request_data)
            if response:
                if response.resultado in ["A", "O"] and response.comprobanteResponse:
                    result = response.comprobanteResponse
                    values = {
                        "l10n_ar_afip_auth_mode": "CAE",
                        "l10n_ar_afip_auth_code": result.CAE and str(result.CAE) or "",
                        "l10n_ar_afip_auth_code_due": result.fechaVencimientoCAE,
                        "l10n_ar_afip_result": response.resultado,
                    }

            if response.arrayObservaciones:
                obs = "".join(
                    [
                        _("\n* Code %s: %s", ob.codigo, ob.descripcion)
                        for ob in response.arrayObservaciones.codigoDescripcion
                    ]
                )
                return_codes += [str(ob.codigo) for ob in response.arrayObservaciones.codigoDescripcion]
            if response.arrayErrores:
                errors = "".join(
                    [
                        _("\n* Code %s: %s", err.codigo, err.descripcion)
                        for err in response.arrayErrores.codigoDescripcion
                    ]
                )
                return_codes += [str(err.codigo) for err in response.arrayErrores.codigoDescripcion]
            if response.evento:
                events = "".join([_("\n* Code %s: %s", response.evento.codigo, response.evento.descripcion)])
                return_codes += [str(response.evento.codigo)]

            return_info = inv._prepare_return_msg(afip_ws, errors, obs, events, return_codes)
            afip_result = values.get("l10n_ar_afip_result")
            xml_response, xml_request = transport.xml_response, transport.xml_request
            if afip_result not in ["A", "O"]:
                if not self.env.context.get("l10n_ar_invoice_skip_commit"):
                    self.env.cr.rollback()
                if inv.exists():
                    # Only save the xml_request/xml_response fields if the invoice exists.
                    # It is possible that the invoice will rollback as well e.g. when it is automatically created:
                    #   * creating credit note with full reconcile option
                    #   * creating/validating an invoice from subscription/sales
                    inv.sudo().write(
                        {
                            "l10n_ar_afip_xml_request": xml_request,
                            "l10n_ar_afip_xml_response": xml_response,
                        }
                    )
                if not self.env.context.get("l10n_ar_invoice_skip_commit"):
                    self.env.cr.commit()  # pylint: disable=invalid-commit
                return return_info
            values.update(
                l10n_ar_afip_xml_request=xml_request,
                l10n_ar_afip_xml_response=xml_response,
            )
            inv.sudo().write(values)
            if return_info:
                inv.message_post(
                    body=Markup("<p><b>%s%s</b></p>") % (_("AFIP Messages"), plaintext2html(return_info, "em"))
                )

    def _get_tributes(self, base_lines=None):
        """Override to add wsmtxca specific format for tributes."""
        res = super()._get_tributes(base_lines=base_lines)
        if self.env.context.get("wsmtxca") and res:
            new_res = []
            for item in res:
                new_res.append(
                    {
                        "codigo": item["Id"],
                        "descripcion": item["Desc"],
                        "baseImponible": item["BaseImp"],
                        "importe": item["Importe"],
                    }
                )
            return new_res
        return res

    def _get_related_invoice_data(self):
        """Override to add wsmtxca specific keys for related invoice data."""
        afip_ws = self.journal_id.l10n_ar_afip_ws
        res = {}
        if afip_ws != "wsmtxca":
            return super()._get_related_invoice_data()

        related_inv = self._found_related_invoice()
        if not related_inv:
            return res

        # Convert keys to wsmtxca format
        wsmtxca_keys = {
            "type": "codigoTipoComprobante",
            "pos_number": "numeroPuntoVenta",
            "number": "numeroComprobante",
            "cuit": "cuit",
            "date": "fechaEmision",
        }

        res.update(
            {
                wsmtxca_keys["type"]: related_inv.l10n_latam_document_type_id.code,
                wsmtxca_keys["pos_number"]: related_inv.journal_id.l10n_ar_afip_pos_number,
                wsmtxca_keys["number"]: self._l10n_ar_get_document_number_parts(
                    related_inv.l10n_latam_document_number,
                    related_inv.l10n_latam_document_type_id.code,
                )["invoice_number"],
            }
        )

        return res

    def _get_line_details(self, base_lines=None):
        """Override to add wsmtxca specific format for line details."""
        base_lines = base_lines or []
        details = super()._get_line_details(base_lines=base_lines)

        if (afip_ws := self.journal_id.l10n_ar_afip_ws) and afip_ws != "wsmtxca":
            return details

        details = []
        price_precision_digits = min(self.env["decimal.precision"].precision_get("Product Price"), 3)

        for base_line in base_lines:
            line = base_line["record"]

            if line.display_type in ("line_section", "line_note"):
                continue

            if line.product_id and not line.product_uom_id.l10n_ar_afip_code:
                raise UserError(_("No AFIP code in %s UOM", line.product_uom_id.name))

            Pro_umed = line.product_uom_id.l10n_ar_afip_code if line.product_id else "00"
            quantity = base_line["quantity"]

            if Pro_umed not in ("97", "99", "00"):
                if line._get_downpayment_lines():
                    Pro_umed = "97"
                elif line.price_unit < 0:
                    Pro_umed = "99"

            is_senia_or_discount = Pro_umed in ("97", "99")
            is_letter_b = self.l10n_latam_document_type_id.code in ("6", "7", "8")

            unit_price_net = float_repr(line.price_unit, precision_digits=price_precision_digits)
            vat_tax = line.tax_ids.filtered(lambda x: x.tax_group_id.l10n_ar_vat_afip_code)

            # IVA amount from tax details
            importeIVA_taxes = sum(
                td["tax_amount_currency"]
                for td in base_line["tax_details"]["taxes_data"]
                if td["tax"].tax_group_id.l10n_ar_vat_afip_code
            )

            if is_letter_b:
                # Letter B: precioUnitario includes IVA, importeIVA is not reported separately
                vat_rate = vat_tax.amount / 100.0 if vat_tax else 0.0
                precioUnitario = float_repr(
                    line.price_unit * (1 + vat_rate),
                    precision_digits=price_precision_digits,
                )
                total_with_iva = base_line["tax_details"]["raw_total_included_currency"]
                discount_amount = base_line["discount"] and (float(precioUnitario) * quantity - total_with_iva) or 0.0
                importeIVA = 0.0
                importeItem = (
                    float(precioUnitario) * quantity - discount_amount if not is_senia_or_discount else total_with_iva
                )
            else:
                # Letter A (and others): precioUnitario is NET (sin IVA), importeIVA reported separately
                precioUnitario = unit_price_net
                # Descuento NETO (sin IVA): precio_truncado * qty - base_neta_cruda
                discount_amount = (
                    base_line["discount"]
                    and (float(unit_price_net) * quantity - base_line["tax_details"]["raw_total_excluded_currency"])
                    or 0.0
                )
                importeIVA = importeIVA_taxes
                # importeItem = base_neta + importeIVA (fórmula AFIP, error 519)
                base_neta = (
                    float(unit_price_net) * quantity - discount_amount
                    if not is_senia_or_discount
                    else base_line["tax_details"]["raw_total_excluded_currency"]
                )
                importeItem = base_neta + importeIVA

            values = {
                "unidadesMtx": "1",
                "codigoMtx": self._get_codigoMtx(line),
                "codigo": line.product_id.default_code or None,
                "descripcion": line.name,
                "codigoUnidadMedida": int(Pro_umed) or 7,
                "cantidad": quantity if not is_senia_or_discount else None,
                "precioUnitario": precioUnitario if not is_senia_or_discount else None,
                "codigoCondicionIVA": vat_tax.tax_group_id.l10n_ar_vat_afip_code,
                "importeItem": float_repr(importeItem, precision_digits=2),
                "importeIVA": float_repr(importeIVA, precision_digits=2) if importeIVA else None,
                "importeBonificacion": float_repr(discount_amount, precision_digits=6) if discount_amount else None,
            }
            details.append(values)

        return details

    def _get_codigoMtx(self, line):
        """Return the codigoMtx that applies.

        Could be the barcode of the product or either the  generic code depending on the type of product/service or
        discounts

        Casos disponibles en ARCA Codigos genericos codigoMtx
        ** 7790001001030, Descuentos y bonificaciones comerciales
        ** 7790001001078, Servicios prestados
        ** 7790001001054, Ventas varias  (lo agregamos  como por defecto cuando no hay producto en linea)

        7790001001047, Conceptos financieros
        7790001001061, Bienes de uso                        (elif line.product_id.is_asset:)
        7790001001085, Fletes                                (Posiblemente lo agreguemos en futuro)
        7790001001092, Alquileres
        7790001001115, Depósito y servicios de logística
        7790001001122, Repuestos y accesorios
        7790001001139, Ajustes impositivos
        7790001001146, Actividades comerciales no codificadas
        7790001001153, Venta de material de rezago
        """
        cod_mtx = ""
        if barcode := line.product_id.barcode:
            if barcode.isdigit() and len(barcode) in (8, 12, 13):
                cod_mtx = barcode.zfill(13)
            else:
                raise UserError(
                    _(
                        "The product %s has an invalid barcode for ARCA (only GS1 o Códigos GTIN 8/12/13)",
                        line.product_id.name,
                    )
                )

        if not cod_mtx:
            if line.product_id.type == "service":
                cod_mtx = "7790001001078"  # Servicios prestados
            elif line.price_total < 0.0:
                cod_mtx = "7790001001030"  # Descuentos y bonificaciones comerciales
            elif not line.product_id:
                cod_mtx = "7790001001054"  # Ventas varias

        if not cod_mtx:
            raise UserError(
                _(
                    "The product '%s' does not have a valid Codigo MTX for ARCA. "
                    "Please set a valid barcode in the product to continue.",
                    line.product_id.name,
                )
            )
        return cod_mtx

    def _get_optionals_data(self):
        """Override to add wsmtxca specific format for optional data."""
        optionals = super()._get_optionals_data()
        afip_ws = self.journal_id.l10n_ar_afip_ws

        if afip_ws != "wsmtxca" or not optionals:
            return optionals

        # Convert to wsmtxca format
        wsmtxca_optionals = []
        for opt in optionals:
            wsmtxca_optionals.append({"t": opt.get("Id"), "c1": opt.get("Valor")})
        return wsmtxca_optionals

    def wsmtxca_get_cae_request(self, client=None):
        """Generate CAE request data for wsmtxca webservice."""
        res = {}
        partner_id_code = self._get_partner_code_id(self.commercial_partner_id)
        base_lines, _tax_lines = self._get_rounded_base_and_tax_lines()
        amounts = self._l10n_ar_get_amounts(base_lines=base_lines)
        related_invoices = self._get_related_invoice_data()
        due_payment_date = self._due_payment_date()
        service_start, service_end = self._service_dates()
        tributes = self.with_context(wsmtxca=True)._get_tributes(base_lines=base_lines)
        vat_data = self._get_vat(base_lines=base_lines)
        temp = []

        WS_DATE_FORMAT = {
            "wsfe": "%Y%m%d",
            "wsfex": "%Y%m%d",
            "wsbfe": "%Y%m%d",
            "wsmtxca": "%Y-%m-%d",
        }

        # Post process vat_data
        # Step 1: modify the keys of the dictionary to make it work with wsmtxca
        vat_needed = ["4", "5", "6"]
        for item in vat_data:
            if "Id" in item and "Importe" in item and item.get("Id") in vat_needed:
                temp.append(
                    {
                        "codigo": item["Id"],
                        "importe": float_repr(item["Importe"], precision_digits=2),
                    }
                )
        vat_data = temp
        # Step 2: ensure that all vat types are present even if amount is 0
        vat_data_keys = [item["codigo"] for item in vat_data]
        vat_code_used = self.line_ids.mapped("tax_ids.tax_group_id.l10n_ar_vat_afip_code")
        for cod_iva in vat_code_used:
            if cod_iva in vat_needed and cod_iva not in vat_data_keys:
                vat_data.append({"codigo": cod_iva, "importe": 0.0})

        ArrayItemsType = client.get_type("ns0:ArrayItemsType")
        ArraySubtotalesIVA = client.get_type("ns0:ArraySubtotalesIVAType")
        ComprobanteAsociadoType = client.get_type("ns0:ArrayComprobantesAsociadosType")
        ArrayOtrosTributosType = client.get_type("ns0:ArrayOtrosTributosType")

        invoice_number = self._l10n_ar_get_document_number_parts(
            self.l10n_latam_document_number, self.l10n_latam_document_type_id.code
        )["invoice_number"]
        vat = partner_id_code and self.commercial_partner_id._get_id_number_sanitize()

        importeGravado = amounts["vat_taxable_amount"]
        importeNoGravado = amounts["vat_untaxed_base_amount"]

        res = {
            "codigoTipoComprobante": int(self.l10n_latam_document_type_id.code),
            "numeroPuntoVenta": int(self.journal_id.l10n_ar_afip_pos_number),
            "numeroComprobante": invoice_number,
            "numeroDocumento": vat and int(vat) or 0,
            "condicionIVAReceptor": int(self.partner_id.l10n_ar_afip_responsibility_type_id.code),
            "fechaEmision": self.invoice_date.strftime(WS_DATE_FORMAT["wsmtxca"]),
            "codigoConcepto": int(self.l10n_ar_afip_concept),
            "codigoTipoDocumento": int(partner_id_code) or 0,
            "codigoMoneda": self.currency_id.l10n_ar_afip_code,
            "cotizacionMoneda": float_repr(1 / self.invoice_currency_rate, precision_digits=6),
            "importeTotal": float_round(self.amount_total, precision_digits=2),
            "importeSubtotal": float_round(
                amounts["vat_taxable_amount"] + amounts["vat_untaxed_base_amount"] + amounts["vat_exempt_base_amount"],
                precision_digits=2,
            ),
            "importeGravado": float_round(importeGravado, precision_digits=2),
            "importeExento": float_round(amounts["vat_exempt_base_amount"], precision_digits=2),
            "importeNoGravado": float_round(importeNoGravado, precision_digits=2),
            "importeOtrosTributos": float_round(amounts["not_vat_taxes_amount"], precision_digits=2)
            if amounts["not_vat_taxes_amount"]
            else None,
            "arrayItems": ArrayItemsType(self._get_line_details(base_lines=base_lines)),
            "arraySubtotalesIVA": ArraySubtotalesIVA(vat_data) if vat_data else None,
            "arrayComprobantesAsociados": ComprobanteAsociadoType([related_invoices]) if related_invoices else None,
            "arrayOtrosTributos": ArrayOtrosTributosType(tributes) if tributes else None,
            "fechaServicioDesde": service_start.strftime(WS_DATE_FORMAT["wsmtxca"]) if service_start else None,
            "fechaServicioHasta": service_end.strftime(WS_DATE_FORMAT["wsmtxca"]) if service_end else None,
            "fechaVencimientoPago": due_payment_date.strftime(WS_DATE_FORMAT["wsmtxca"]) if due_payment_date else None,
        }
        if self.l10n_latam_document_type_id.code in ["201", "206"]:  # WSMT148
            res.update({"fechaVencimientoPago": self._due_payment_date().strftime(WS_DATE_FORMAT["wsmtxca"])})

        optionals = self._get_optionals_data()
        if optionals:
            ArrayDatosAdicionalesType = client.get_type("ns0:ArrayDatosAdicionalesType")
            res.update({"arrayDatosAdicionales": ArrayDatosAdicionalesType(optionals) if optionals else None})

        if res.get("codigoMoneda") != "PES" and res["codigoTipoComprobante"] in (
            1,
            6,
            51,
            201,
            206,
        ):
            res["cancelaEnMismaMonedaExtranjera"] = {"Yes": "S", "No": "N"}.get(self.l10n_ar_payment_foreign_currency)

        return res
