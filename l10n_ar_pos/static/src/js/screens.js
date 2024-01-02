odoo.define('l10n_ar_pos.screens', function (require) {
    var screens = require('point_of_sale.screens');
    var rpc = require('web.rpc');
    var core = require('web.core');
    var qweb = core.qweb;
    var _t = core._t;

    screens.ReceiptScreenWidget.include({
        // TODO: este método estaba en v11, en v13 parecería que paso a llamarse print_html, revisar
        print_xml: function () {
            var self = this;
            if (this.pos.config.receipt_invoice_number) {
                self.receipt_data = this.get_receipt_render_env();
                var order = this.pos.get_order();
                return rpc.query({
                    // IMPORTANTISIMO ****************************
                    // DESDE ESTE MODELO SE ESTA IMPORTANDO account_move para relacionar
                    //
                    model: 'pos.order',
                    method: 'search_read',
                    domain: [['pos_reference', '=', order['name']]],
                    fields: ['account_move'],
                }).then(function (orders) {
                    if (orders.length > 0) {
                        if (orders[0]['account_move']) {
                            // el array 1 de Split es el que tiene el nro!
                            var invoice_number = orders[0]['account_move'][1].split(" ")[1];
                            var invoice_letter = orders[0]['account_move'][1].split(" ")[0].substring(3, 4);
                            var account_move = orders[0]['account_move'][0]
                            self.receipt_data['order']['invoice_number'] = invoice_number;
                            self.receipt_data['order']['invoice_letter'] = invoice_letter;
                            //----
                            var company_id = self['pos']['company']['id'];
                            var partner_id = self['pos']['company']['partner_id'][0];
                            rpc.query({
                                 model: 'res.company',
                                 method: 'search_read',
                                 args: [[['id', '=', company_id]], ['l10n_ar_afip_start_date']],
                            }).then(function (company_dict) {
                                self.pos.get_order()['l10n_ar_afip_start_date'] = company_dict[0]['l10n_ar_afip_start_date'];

                                rpc.query({
                                     model: 'res.partner',
                                     method: 'search_read',
                                     args: [[['id', '=', partner_id]], ['vat',
                                                                        'l10n_ar_gross_income_number',
                                                                        'l10n_ar_afip_responsibility_type_id',
                                                                        'street', 'city', 'state_id', 'country_id', 'company_registry']],
                                    }

                                 ).then(function (company_partner) {
                                    self.receipt_data['order']['vat'] = company_partner[0]['vat'];
                                    self.receipt_data['order']['l10n_ar_gross_income_number'] = company_partner[0]['l10n_ar_gross_income_number'];
                                    self.receipt_data['order']['l10n_ar_afip_start_date'] = company_partner[0]['l10n_ar_afip_start_date'];
                                    self.receipt_data['order']['l10n_ar_afip_responsibility_type_id'] = company_partner[0]['l10n_ar_afip_responsibility_type_id'][1];
                                    self.receipt_data['order']['street'] = company_partner[0]['street'] + ', ' +
                                                                     company_partner[0]['city'] + ', ' +
                                                                     company_partner[0]['state_id'][1] + ', ' +
                                                                     company_partner[0]['country_id'][1];
                                    self.receipt_data['order']['company_registry'] = company_partner[0]['company_registry'];
                                    //---------
                                    rpc.query({
                                         model: 'account.move',
                                         method: 'search_read',
                                         args: [[['id', '=', account_move]], ['l10n_ar_afip_auth_code',
                                                                            'l10n_ar_afip_auth_code_due',
                                                                            'l10n_ar_afip_qr_code',
                                                                            'l10n_latam_document_type_id',
                                                                            ]],
                                        }

                                     ).then(function (invoices) {
                                        self.receipt_data['order']['l10n_ar_afip_qr_code'] = invoices[0]['l10n_ar_afip_qr_code'];
                                        self.receipt_data['order']['l10n_ar_afip_auth_code'] = invoices[0]['l10n_ar_afip_auth_code'];
                                        self.receipt_data['order']['l10n_ar_afip_auth_code_due'] = invoices[0]['l10n_ar_afip_auth_code_due'];
                                        self.receipt_data['order']['l10n_latam_document_type_id'] = invoices[0]['l10n_latam_document_type_id'][1].split(" ")[0];
                                        var receipt = qweb.render('XmlReceipt', self.receipt_data);
                                        self.pos.proxy.print_receipt(receipt);
                                     });
                                 });
                            });
                        }
                    }
                });
            } else {
                this._super();
            }
        },
        // CON LA FUNCION RENDER_RECEIPT deben traerse los modelos para poder usar en el recibo
        render_receipt: function () {
            this._super();
            var self = this;
            var order = this.pos.get_order(); // Ok!!

            if (!this.pos.config.iface_print_via_proxy && this.pos.config.receipt_invoice_number && order.is_to_invoice()) {
                var invoiced = new $.Deferred();
                rpc.query({
                    // IMPORTANTISIMO ****************************
                    // DESDE ESTE MODELO SE ESTA IMPORTANDO account_move para relacionar
                    //
                    model: 'pos.order',
                    method: 'search_read',
                    domain: [['pos_reference', '=', order['name']]],
                    // account_move es un campo nativo de pos.order
                    fields: ['account_move']
                }).then(function (orders) {
                    if (orders.length > 0 && orders[0]['account_move'] && orders[0]['account_move'][1]) {
                        var invoice_number = orders[0]['account_move'][1].split(" ")[1];
                        var invoice_letter = orders[0]['account_move'][1].split(" ")[0].substring(3, 4);
                        var account_move = orders[0]['account_move'][0]
                        self.pos.get_order()['invoice_number'] = invoice_number;
                        self.pos.get_order()['invoice_letter'] = invoice_letter;
                        //----
                        var company_id = self['pos']['company']['id'];
                        var partner_id = self['pos']['company']['partner_id'][0];

                        rpc.query({
                             model: 'res.company',
                             method: 'search_read',
                             args: [[['id', '=', company_id]], ['l10n_ar_afip_start_date', 'company_registry']],
                            }).then(function (company_dict) {
                             self.pos.get_order()['l10n_ar_afip_start_date'] = company_dict[0]['l10n_ar_afip_start_date'];
                             self.pos.get_order()['company_registry'] = company_dict[0]['company_registry'];
                             rpc.query({
                                 model: 'res.partner',
                                 method: 'search_read',
                                 args: [[['id', '=', partner_id]], ['vat',
                                                                    'l10n_ar_gross_income_number',
                                                                    'l10n_ar_afip_responsibility_type_id',
                                                                    'street', 'city', 'state_id', 'country_id']],
                                }

                             ).then(function (company_partner) {
                                self.pos.get_order()['vat'] = company_partner[0]['vat'];
                                self.pos.get_order()['l10n_ar_gross_income_number'] = company_partner[0]['l10n_ar_gross_income_number'];
                                self.pos.get_order()['l10n_ar_afip_responsibility_type_id'] = company_partner[0]['l10n_ar_afip_responsibility_type_id'][1];
                                self.pos.get_order()['street'] = company_partner[0]['street'] + ', ' +
                                                                 company_partner[0]['city'] + ', ' +
                                                                 company_partner[0]['state_id'][1] + ', ' +
                                                                 company_partner[0]['country_id'][1];
                                //---------
                                rpc.query({
                                     model: 'account.move',
                                     method: 'search_read',
                                     args: [[['id', '=', account_move]], ['l10n_ar_afip_auth_code',
                                                                        'l10n_ar_afip_auth_code_due',
                                                                        'l10n_ar_afip_qr_code',
                                                                        'l10n_latam_document_type_id',
                                                                        'invoice_date',
                                                                        ]],
                                    }

                                 ).then(function (invoices) {
                                    console.log('invoices', invoices);
                                    self.pos.get_order()['l10n_ar_afip_qr_code'] = invoices[0]['l10n_ar_afip_qr_code'];
                                    self.pos.get_order()['l10n_ar_afip_auth_code'] = invoices[0]['l10n_ar_afip_auth_code'];
                                    self.pos.get_order()['l10n_ar_afip_auth_code_due'] = invoices[0]['l10n_ar_afip_auth_code_due'];
                                    self.pos.get_order()['l10n_latam_document_type_id'] = invoices[0]['l10n_latam_document_type_id'][1].split(" ")[0];
                                    self.pos.get_order()['invoice_date'] = invoices[0]['invoice_date'];
                                    self.$('.pos-receipt-container').html(qweb.render('OrderReceipt', self.get_receipt_render_env()));

                                 });
                             });
                            });
                    }
                    invoiced.resolve();
                }).catch(function (type, error) {
                    invoiced.reject(error);
                });
                return invoiced;
            } else {
                this._super();
            }
        }
    })

    screens.ClientListScreenWidget.include({
        save_client_details: function (partner) {
            var self = this;
            var fields = {};
            this.$('.client-details-contents .detail').each(function(idx,el){
                if (self.integer_client_details.includes(el.name)){
                    var parsed_value = parseInt(el.value, 10);
                    if (isNaN(parsed_value)){
                        fields[el.name] = false;
                    }
                    else{
                        fields[el.name] = parsed_value
                    }
                }
                else{
                    fields[el.name] = el.value || false;
                }
            });
            // If the responsibility type is "responsable inscripto", then the document number is required.
            if (!fields.vat && fields.l10n_ar_afip_responsibility_type_id == '1' ) {
                this.gui.show_popup('error',_t('For the selected AFIP Responsibility el campo "Document number" es requerido.'));
                return;
            }
            // If the responsibility type is "responsable inscripto", then the document type should be CUIT.
            if (fields.l10n_latam_identification_type_id != '4' && fields.l10n_ar_afip_responsibility_type_id == '1' ) {
                this.gui.show_popup('error',_t('For the selected AFIP Responsibility you will need to set CUIT Identification Type'));
                return;
            }
            this._super(partner);
        },
    });

});
