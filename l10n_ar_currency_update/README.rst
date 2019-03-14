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

This will add AFIP Web Service as your currency provider (official argentinian provider).

By default the automatic rate updates are inactive, you can active them by company
by going to *Accounting / Configuration / Settings* menu and there found and set
the *Interval* and *Next Run* date in the *Automatic Currecy Rates* section
(dont forget to click Save button)

When actived the currency rates of your companies will be updated automatically.
We recommend to use daily interval since AFIP update the rates daily.

The scheduled action that will be run to update the currency rates will be run
after 21 hours (GMT-3), this is required since the rates are published by
AFIP after 9 pm.

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
