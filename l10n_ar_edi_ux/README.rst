.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

===================================
Argentinian Electronic Invoicing UX
===================================

This module extends the functionality of the Argentinian Electronic Invoicing (EDI) system with improved user experience features and additional functionality for ARCA (Federal Administration of Public Revenues) integration.

**Main Features:**

* **Enhanced Credit/Debit Notes:** Adds associated period fields (l10n_ar_afip_asoc_period_start / l10n_ar_afip_asoc_period_end) for better ARCA reporting when no related invoice exists
* **Improved Document Linking:** Enhanced auto-detection of linked documents when posting credit/debit notes to ARCA by checking linked invoices on sale orders
* **ARCA Padron Integration:** Complete logic to connect to ARCA Padron using the connection approach from the enterprise l10n_ar_edi module
* **Journal Web Services:** Adds functionality to electronic journals to get valid document types for selected web services with user-friendly response messages
* **Export Documentation:** Support for boarding permissions (Permisos de embarque) in Argentinian electronic export invoices
* **Partner Data Synchronization:** Automated partner data updates from ARCA Padron with configurable title case formatting

ARCA Padron Integration
=======================

This module provides comprehensive integration with ARCA's Padron system for automatic partner data synchronization:

**Configuration Options:**

* **Title Case Formatting:** To disable title case formatting for ARCA retrieved data, create or modify the system parameter "use_title_case_on_padron_afip" with value False (default: True)

**Data Update Methods:**

1. **Individual Partner Update:** From any partner with a configured CUIT, click the "Update from ARCA" button to synchronize data
2. **Bulk Update:** Use the mass update wizard available in the Partners menu

**Testing Environment:**

For testing environments, you can use the following test CUITs for the 'ws_sr_constancia_inscripcion' padron service:

* Test CUITs are available in the internal Argentina Localization documentation, section "Padrón Datos Contacto"
* Documentation link: https://www.adhoc.inc/odoo/action-7014/139/knowledge/2109

**Boarding Permissions (Export Documentation):**

For export invoices, you can configure boarding permissions (Permisos de embarque) that will be included in the electronic invoice when:

* The invoice is an export invoice
* The ARCA concept is 'Products / Definitive export of goods'

Installation
============

This module is auto-installed when both l10n_ar_ux and l10n_ar_edi modules are installed.

**Prerequisites:**

* l10n_ar_ux: Argentina Localization UX
* l10n_ar_edi: Argentina Electronic Invoicing (Enterprise)
* account_accountant: Accounting features

Configuration
=============

**ARCA Connection Setup:**

1. Configure your ARCA certificates and connection settings in the base l10n_ar_edi module
2. Ensure your company has a valid CUIT configured

**Optional Settings:**

1. **Padron Title Case:** Go to Settings > Technical > Parameters > System Parameters

   * Create parameter: `use_title_case_on_padron_afip`
   * Value: `False` to disable title case formatting (default: `True`)

2. **Foreign Currency Policy:** The module automatically sets the default foreign currency payment policy for Argentine companies during installation

**Boarding Permissions Setup:**

1. Go to Accounting > Configuration > Argentina > Boarding Permissions
2. Create boarding permissions for your export operations
3. Associate them with export invoices as needed

Usage
=====

**Partner Data Synchronization:**

1. **Individual Update:**

   * Open any partner record with a CUIT
   * Click "Update from ARCA" button
   * Review and confirm the data in the wizard

2. **Electronic Journal Configuration:**

   * Go to Accounting > Configuration > Journals
   * Select an electronic journal
   * Use the "Get Valid Document Types" button to retrieve ARCA web service information

**Credit/Debit Notes with Associated Periods:**

1. Create a credit or debit note
2. If no related invoice exists, set the "Associated Period Start" and "Associated Period End" fields
3. These fields will be included in the ARCA electronic submission

**Export Invoices with Boarding Permissions:**

1. Create an export invoice
2. Set the ARCA concept to "Products / Definitive export of goods"
3. Add the relevant boarding permissions in the "Permiso de Embarque" field
4. The boarding permission information will be included in the electronic invoice

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/odoo-argentina-ee/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us by providing a detailed and welcomed feedback.

Credits
=======

Authors
~~~~~~~

* ADHOC SA

Contributors
~~~~~~~~~~~~

* ADHOC SA Development Team

Images
------

* |company| |icon|

Maintainer
----------

|company_logo|

This module is maintained by |company|.

|company| specializes in Odoo implementations and provides comprehensive ERP solutions
for businesses in Argentina and Latin America.

To contribute to this module, please visit https://www.adhoc.com.ar.
