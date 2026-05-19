.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

=====================================================
Argentinean Electronic Invoicing - WSMTXCA Webservice
=====================================================

Extends the Argentinean Electronic Invoicing (l10n_ar_edi) to add support for the WSMTXCA webservice (RG2904 - Codificación de producto).

Installation
============

To install this module, you need to:

#. Install the module from the Apps menu.

Configuration
=============

To configure this module, you need to:

#. Configure your AFIP certificate in *Accounting > Configuration > Settings* (inherited from l10n_ar_edi).
#. Create or edit a Sales Journal and set **AFIP POS System** to ``Codificación de producto - Web Service (WSMTXCAWS)``.
#. Set the **AFIP POS Number** according to your AFIP portal configuration.
#. Set the **MTXCA product code** (``codigoMtx``) on each product used in invoices issued through this webservice.
   This code is company-specific and must be loaded in the **Barcode** field of the product.
   Each company must register its own product codes with AFIP.

   For testing purposes or lines without a specific product, the following generic codes provided by ARCA are available:

   ========================  =====================================================
   Código (codigoMtx)        Descripción
   ========================  =====================================================
   7790001001030             Descuentos y bonificaciones comerciales
   7790001001078             Servicios prestados
   7790001001054             Ventas varias *(usado por defecto cuando la línea no tiene producto)*
   7790001001047             Conceptos financieros
   7790001001061             Bienes de uso
   7790001001085             Fletes
   7790001001092             Alquileres
   7790001001115             Depósito y servicios de logística
   7790001001122             Repuestos y accesorios
   7790001001139             Ajustes impositivos
   7790001001146             Actividades comerciales no codificadas
   7790001001153             Venta de material de rezago
   ========================  =====================================================

Usage
=====

Once configured, the module handles WSMTXCA electronic invoicing automatically when validating invoices
from a journal with the ``WSMTXCAWS`` POS system:

#. Create an invoice in a journal configured with the WSMTXCAWS POS system.
#. Validate the invoice. The module will contact the WSMTXCA webservice and request a CAE.
#. To consult a previously authorized invoice, use *Accounting > Reporting > AFIP WS Consult*.
#. To check available AFIP POS numbers for the webservice, use the **Check Available AFIP PoS** button on the journal (production mode only).
#. To consult the exchange rate for a currency via WSMTXCA, use the currency rate consultation feature on the currency record.

Technical
=========

The module implements the following model extensions:

* ``account.move``: overrides ``_l10n_ar_do_afip_ws_request_cae`` to handle WSMTXCA-specific CAE requests (``autorizarComprobante``), response parsing, and tribute/tax formatting.
* ``account.journal``: adds the ``WSMTXCAWS`` POS system option, maps it to the ``wsmtxca`` webservice, implements ``_wsmtxca_convert_auth`` for WSMTXCA authentication, and overrides ``l10n_ar_check_afip_pos_number`` and ``_l10n_ar_get_afip_last_invoice_number`` for WSMTXCA.
* ``res.currency``: overrides ``_l10n_ar_get_afip_ws_currency_rate`` to query exchange rates via the WSMTXCA ``consultarCotizacionMoneda`` service.
* ``l10n_ar.afipws.connection``: overrides ``_l10n_ar_get_afip_ws_url`` to register the WSMTXCA WSDL endpoints for production and testing environments.
* ``l10n_ar_afip.ws.consult`` (wizard): extends the invoice consultation wizard to support the ``WSMTXCAWS`` POS system, delegating to ``consultarComprobante`` on the WSMTXCA service.

WSMTXCA endpoints:

* Production: ``https://serviciosjava.afip.gob.ar/wsmtxca/services/MTXCAService?wsdl``
* Testing: ``https://fwshomo.afip.gov.ar/wsmtxca/services/MTXCAService?wsdl``

For official AFIP documentation see: https://www.afip.gob.ar/ws/documentacion/ws-mtxca.asp

Credits
=======

Images
------

* |company| |icon|

Contributors
------------

Maintainer
----------

|company_logo|

This module is maintained by the |company|.

To contribute to this module, please visit https://www.adhoc.com.ar.
