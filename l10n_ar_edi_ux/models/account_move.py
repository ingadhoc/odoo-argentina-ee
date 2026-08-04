from odoo import _, api, fields, models
from odoo.addons.l10n_ar_edi.models.account_move import WS_DATE_FORMAT
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ar_afip_asoc_period_start = fields.Date(
        string="Associated Period Start",
        copy=False,
        help="Set this field if it is you are reporting debit/credit note and have not related invoice."
        ' IMPORTANT: This is only applies on "Electronic Invoice - Web Service"',
    )
    l10n_ar_afip_asoc_period_end = fields.Date(
        string="Associated Perdio End",
        copy=False,
        help="Set this field if it is you are reporting debit/credit note and have not related invoice."
        ' IMPORTANT: This is only applies on "Electronic Invoice - Web Service"',
    )
    l10n_ar_boarding_permission_ids = fields.Many2many(
        "l10n_ar.boarding_permission",
        string="Boarding Permission",
        check_company=True,
        ondelete="restrict",
        help="This information is only sent if the invoice is an export invoice and the 'AFIP Concept' is 'Products / Definitive export of goods'.",
    )

    # Esto se podria sugerir para hacerlo en odoo oficial
    l10n_ar_afip_service_start = fields.Date(copy=False)
    l10n_ar_afip_service_end = fields.Date(copy=False)

    def _found_related_invoice(self):
        """
        TODO borrar cuando se mezcle https://github.com/odoo/enterprise/pull/12972/files
        """
        res = super()._found_related_invoice()
        if (
            not res
            and self.l10n_latam_document_type_id.internal_type in ["credit_note", "debit_note"]
            and self.sudo().env.ref("base.module_sale").state == "installed"
        ):
            original_entry = (
                self.mapped("invoice_line_ids.sale_line_ids.invoice_lines")
                .filtered(
                    lambda x: (
                        x.move_id.l10n_latam_document_type_id.country_id.code == "AR"
                        and x.move_id.l10n_latam_document_type_id.internal_type
                        != self.l10n_latam_document_type_id.internal_type
                        and x.move_id.l10n_ar_afip_result in ["A", "O"]
                        and x.move_id.l10n_ar_afip_auth_code
                    )
                )
                .mapped("move_id")
            )
            return original_entry and original_entry[0] or res
        return res

    def _get_partner_code_id(self, partner):
        # Odoo 19.0 returns an implicit None when the partner's identification type
        # has no ARCA code (e.g. generic "VAT" on foreign partners of export invoices),
        # crashing int() in _compute_l10n_ar_afip_qr_code. Restore the 17.0/18.0
        # behavior of returning a falsy value that int() accepts.
        return super()._get_partner_code_id(partner) or False

    def _check_vat_condition(self):
        """Return the AFIP code of the VAT condition of the partner"""
        self.ensure_one()
        vat_condition = self.partner_id.l10n_ar_afip_responsibility_type_id.code
        if not vat_condition:
            raise UserError(
                _(
                    "The partner %s does not have an ARCA Responsibility configured. Please set the ARCA Responsibility Type in the partner's configuration to validate the invoice."
                )
                % self.partner_id.name
            )

    @api.model
    def wsfe_get_cae_request(self, client=None):
        res = super().wsfe_get_cae_request(client=client)
        if self.l10n_latam_document_type_id.internal_type in ["credit_note", "debit_note"]:
            related_invoices = self._get_related_invoice_data()
            if not related_invoices and self.l10n_ar_afip_asoc_period_start and self.l10n_ar_afip_asoc_period_end:
                res.get("FeDetReq")[0].get("FECAEDetRequest").update(
                    {
                        "PeriodoAsoc": {
                            "FchDesde": self.l10n_ar_afip_asoc_period_start.strftime(WS_DATE_FORMAT["wsfe"]),
                            "FchHasta": self.l10n_ar_afip_asoc_period_end.strftime(WS_DATE_FORMAT["wsfe"]),
                        }
                    }
                )
        return res

    def _l10n_ar_do_afip_ws_request_cae(self, client, auth, transport):
        """Check if the partner has CondicionIVAReceptorId configured."""
        for inv in self.filtered(lambda x: x.journal_id.l10n_ar_afip_ws and not x.l10n_ar_afip_auth_code):
            inv._check_vat_condition()
        return super()._l10n_ar_do_afip_ws_request_cae(client, auth, transport)

    def _post(self, soft=True):
        """Be able to validate electronic vendor bills that are type ARCA POS"""
        purchase_ar_edi_invoices = self.filtered(
            lambda x: x.journal_id.type == "purchase" and x.journal_id.l10n_ar_is_pos and x.journal_id.l10n_ar_afip_ws
        )

        # Send invoices to ARCA and get the return info
        validated = error_vendor_bill = self.env["account.move"]
        for bill in purchase_ar_edi_invoices:
            # If we are on testing environment and we don't have certificates we validate only locally.
            # This is useful when duplicating the production database for training purpose or others
            if bill._is_dummy_afip_validation():
                bill._dummy_afip_validation()
                super(AccountMove, bill)._post(soft=soft)
                validated += bill
                continue

            client, auth, transport = bill.company_id._l10n_ar_get_connection(
                bill.journal_id.l10n_ar_afip_ws
            )._get_client(return_transport=True)
            super(AccountMove, bill)._post(soft=soft)
            return_info = bill._l10n_ar_do_afip_ws_request_cae(client, auth, transport)
            if return_info:
                error_vendor_bill = bill
                break
            validated += bill

            # If we get CAE from AFIP then we make commit because we need to save the information returned by AFIP
            # in Odoo for consistency, this way if an error ocurrs later in another invoice we will have the ones
            # correctly validated in AFIP in Odoo (CAE, Result, xml response/request).
            if not self.env.context.get("l10n_ar_invoice_skip_commit"):
                # TODO ver de utilizar savepoints: https://github.com/OCA/odoo-community.org/blob/master/website/Contribution/CONTRIBUTING.rst#never-commit-the-transaction
                self.env.cr.commit()  # pragma pylint: disable=invalid-commit

        if error_vendor_bill:
            msg = (
                _("We could not validate the vendor bill in AFIP")
                + (
                    _(' "%s" %s. ') % (error_vendor_bill.partner_id.name, error_vendor_bill.display_name)
                    if error_vendor_bill.exists()
                    else _(". ")
                )
                + _("This is what we get:\n%s\n\nPlease make the required corrections and try again") % (return_info)
            )
            # if we've already validate any invoice, we've commit and we want to inform which invoices were validated
            # which one were not and the detail of the error we get. This ins neccesary because is not usual to have a
            # raise with changes commited on databases
            if validated:
                unprocess = self - validated - error_vendor_bill
                msg = _(
                    "Some vendor bills where validated in AFIP but as we have an error with one vendor bill the batch validation was stopped\n"
                    "\n* These vendor bills were validated:\n   * %s\n"
                    % ("\n   * ".join(validated.mapped("name")))
                    + "\n* These vendor bills weren't validated:\n%s\n"
                    % (
                        "\n".join(
                            [
                                '   * %s: "%s" amount %s'
                                % (item.display_name, item.partner_id.name, item.amount_total_signed)
                                for item in unprocess
                            ]
                        )
                    )
                    + "\n\n\n"
                    + msg
                )
            raise UserError(msg)

        return super(AccountMove, self - purchase_ar_edi_invoices)._post(soft=soft)

    def _get_permissions(self):
        """Get 'permiso de embarque' for foreign invoices."""
        self.ensure_one()
        res = []
        invalid_permissions = self.check_valid_boarding_permission()
        if invalid_permissions:
            invalid_permissions_str = "\n".join(invalid_permissions)
            raise UserError(_("Invalid boarding permissions:\n %s") % invalid_permissions_str)
        for permiso in self.l10n_ar_boarding_permission_ids:
            res.append({"Id_permiso": permiso.number, "Dst_merc": permiso.dst_country.l10n_ar_afip_code})
        return res

    @api.model
    def wsfex_get_cae_request(self, last_id, client):
        """Set permiso de embarque to foreign invoice."""
        res = super(AccountMove, self).wsfex_get_cae_request(last_id, client)
        if int(self.l10n_latam_document_type_id.code) == 19 and int(self.l10n_ar_afip_concept) == 1:
            ArrayOfPermisions = client.get_type("ns0:ArrayOfPermiso")
            permisos = self._get_permissions()
            permiso_existente = "S" if permisos else "N"
            res.update({"Permisos": ArrayOfPermisions(permisos) if permisos else None})
            res.update({"Permiso_existente": permiso_existente})
        return res

    def check_valid_boarding_permission(self):
        """This method is used to verify that the Permisos de embarque entered on the export invoice are valid. Receives the authentication credentials, cuit of the represented user, código de despacho and destination country and verifies their existence in the base de datos aduanera."""
        client, auth = self.company_id._l10n_ar_get_connection(self.journal_id.l10n_ar_afip_ws)._get_client()
        valid_permissions = []
        invalid_permissions = []
        for perm in self.l10n_ar_boarding_permission_ids:
            response = client.service["FEXCheck_Permiso"](
                auth, ID_Permiso=perm.number, Dst_merc=int(perm.dst_country.l10n_ar_afip_code)
            )
            permission_status = response["FEXResultGet"]["Status"]
            if permission_status == "OK":
                valid_permissions.append(perm.display_name)
            else:
                invalid_permissions.append(perm.display_name)
        valid_permissions_str = ", ".join(valid_permissions)
        invalid_permissions_str = ", ".join(invalid_permissions)
        msg = (
            _("Valid boarding permissions: %s") % valid_permissions_str
            + _(". Invalid boarding permissions: %s") % invalid_permissions_str
        )
        self.message_post(body=msg)
        return invalid_permissions

    def _is_dummy_afip_validation(self):
        # EXTENDS l10n_ar_edi
        """Original method was not compatible with the new branch approarch.

        With this extension we modify that logic: if we have not certificate, but have an ancestor
        (parent, grandparent, …) that has certificate and shares the same CUIT, we skip the dummy
        and force to continue with afip validation.  This supports multi-level branch hierarchies."""
        self.ensure_one()
        company = self.company_id
        if (
            company._get_environment_type() == "testing"
            and not company.sudo().l10n_ar_afip_ws_crt_id
            and company._l10n_ar_get_cert_ancestor()
        ):
            return False
        return super()._is_dummy_afip_validation()

    def action_post(self):
        for move in self.filtered(lambda x: x.journal_id.l10n_ar_is_pos and x.journal_id.l10n_ar_afip_ws):
            # If the related document (e.g., the source invoice of an electronic
            # credit/debit note) is still in draft state, it does not yet have a
            # definitive number or date, causing the AFIP related-document payload
            # generation to fail with a generic error. Validate this condition upfront
            # and provide a clear message indicating that the related document must be
            # posted first.
            related_inv = move._found_related_invoice()
            if related_inv and related_inv.state != "posted" and not self.env.context.get("invoice_gathering"):
                raise UserError(
                    _(
                        "Cannot electronically validate '%(move)s' because the related "
                        "document '%(related)s' is still in draft state. Please post the "
                        "related document before issuing the electronic credit/debit note.",
                        move=move.display_name,
                        related=related_inv.display_name,
                    )
                )

        return super().action_post()
