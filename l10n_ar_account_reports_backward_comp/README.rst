.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-LGPL--3-blue.png
   :target: https://www.gnu.org/licenses/lgpl-3.0-standalone.html
   :alt: License: LGPL-3

=========================================================
Backward Compatibility for Tax Settlements on Argentina
=========================================================

This module provides backward compatibility for Argentinian tax settlements and accounting reports when migrating from previous versions of Odoo.

Installation
============

This module is auto-installed when both ``l10n_ar_tax_backward_compatibility`` and ``l10n_ar_account_reports`` are installed.

Configuration
=============

No additional configuration is required. The module works automatically once installed.

Usage
=====

The module works automatically in the background to ensure seamless operation with migrated tax data:

**Copying Invoices with Migrated Taxes**

When duplicating an invoice that contains archived backward taxes:

* The module identifies taxes marked as ``is_backward_tax``
* Searches for corresponding partner taxes (perceptions/withholdings) configured on the contact
* Replaces backward taxes with active partner taxes when found
* Removes backward taxes that have no corresponding partner tax configuration
* Posts a message on the invoice documenting the changes made

**Tax Settlement Calculations**

When calculating tax settlements, the module:

* Resolves backward taxes to their current equivalents
* Uses partner-specific tax configurations when available
* Ensures proper tax amount calculations for migrated data
* Handles both perceptions and withholdings correctly

Known Issues / Roadmap
======================

* If generating TXT files becomes complicated, you can generate the file in the previous version and merge it with records from the new version.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/adhoc-dev/odoo-argentina-ee/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and welcomed feedback.

Credits
=======

Authors
~~~~~~~

* ADHOC SA

Contributors
~~~~~~~~~~~~

* ADHOC SA <https://www.adhoc.com.ar>

Maintainer
~~~~~~~~~~

|company_logo|

This module is maintained by ADHOC SA.

To contribute to this module, please visit https://www.adhoc.com.ar.
