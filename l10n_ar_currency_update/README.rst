.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

================================
Argentinian Currency Rate Update
================================

This module integrates ARCA Web Service as the official Argentinian currency provider for automatic exchange rate updates.
This is needed to have a valid ARCA certificate must be configured in the company settings

**Setup:**
By default, automatic rate updates are disabled. To enable them:

#. Go to *Accounting / Configuration / Settings*
#. Locate the *Automatic Currency Rates* section
#. Configure the *Interval* (recommended: daily) and *Next Run* date
#. Click *Save*

**Operation:**
* Currency rates are automatically updated for all active currencies in your companies
* Updates occur after 21:00 GMT-3, when ARCA publishes new rates
* Rates are sourced from the official ARCA exchange service

**Rate Verification:**
Current exchange rates can be verified at: https://www.afip.gob.ar/aduana/cotizacionesMaria/

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

#. Already configured to update currency rates one per day, you can change
   this configurations going to General Settings / Invoicing / Automatic
   currency Rates section.

Usage
=====

Este modulo permite la actualización automática del tipo de cambio de las monedas que esten activadas, tomando la información desde la pagina de AFIP, la cual coincide con la del banco nación, tipo de cambio DIVISA de venta.

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/odoo-argentina/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

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
