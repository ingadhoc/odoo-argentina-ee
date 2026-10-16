.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

=====================================
Argentinian Importing Bills from ARCA
=====================================

This module imports sale and purchase invoices from the spreadsheet that ARCA exports from "Mis Comprobantes".

Key Features
------------

* Import from a journal: drop the ARCA spreadsheet (.xlsx) on a purchase journal, or on a sale journal that is not a point of sale journal. Other attachments (PDF, images) keep the standard Odoo flow.
* Initial setup import from the accounting import guide ("Import Sales from ARCA" and "Import Purchases from ARCA"), for invoices dated before the accounting start date, with a counterpart account for the opening balance (by default, the undistributed profits account).
* Preview before confirming: shows how many invoices will be created and how many already exist in Odoo.
* Option to validate the imported invoices automatically.
* Available for Argentinian companies with VAT responsibility "IVA Responsable Inscripto", "IVA Sujeto Exento" or "Responsable Monotributo".

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

#. Nothing to configure. For the initial setup import, the fiscal periods (accounting start date) must be set first.

Usage
=====

To use this module, you need to:

#. Download the "Mis Comprobantes" spreadsheet (received or issued) from ARCA.
#. Go to Accounting dashboard and drop the file on the purchase or sale journal.
#. Review the invoices to create and confirm.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/odoo-argentina-ee/issues>`_. In case of trouble, please
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
