.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-LGPL--3-blue.png
   :target: https://www.gnu.org/licenses/lgpl
   :alt: License: LGPL-3

================================
Argentinian Currency Rate Update
================================

This module extends the native Odoo currency provider *[AR] ARCA* with what Argentinian companies need:

* ARCA is asked once, with a company that has a valid ARCA certificate, so it works with several Argentinian companies
* Currencies without ARCA code are skipped instead of stopping the whole update
* Only today's rate is saved. If ARCA has not published it yet, a cron retries every 3 hours
* A rate already loaded for the day is not overwritten
* A percentage and a surcharge per company can be added to the ARCA rate
* The name of a currency with ARCA code cannot be changed, because the rate update and electronic invoicing use it

ARCA publishes the new rates after 21:00 (GMT-3). They can be checked at: https://www.afip.gob.ar/aduana/cotizacionesMaria/

Installation
============

To install this module, you need to:

#. Only need to install the module. It is installed automatically with the Argentinian electronic invoicing and the automatic currency rates.

Configuration
=============

To configure this module, you need to:

#. Set a valid ARCA certificate in the company.
#. Go to *Accounting / Configuration / Settings*, *Automatic Currency Rates* section, choose *[AR] ARCA* as service and set the *Interval* (recommended: daily).
#. Optionally, with developer mode, set the percentage and the surcharge to add to the ARCA rate in the same section.

Usage
=====

The rates of the active currencies are updated automatically from ARCA, with the official selling rate (the same as Banco Nación).

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
