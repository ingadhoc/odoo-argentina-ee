.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

============================================
Accounting Reports with Accounting Documents
============================================

Customizes Odoo standard accounting reports to meet specific Argentine requirements, adding necessary fiscal information for balance presentation and generating additional reports for check control.

Functional description
======================

This module adds two main functionalities:

**1. Partner Ledger Report Enhancement**

Modifies the native Partner Ledger (Libro Mayor de Empresas) report to include Argentine fiscal information alongside each partner's name. The standard Odoo report only shows "Partner Name", while with this module it displays "Partner Name (CUIT: 1234567890)".

This functionality is essential for fiscal compliance in Argentina, as the report serves as the official detail of Debtors and Creditors at year-end, required for Annual Balance presentation to accounting and tax authorities.

Agrega el CUIT de cada partner en el reporte "Libro Mayor de Empresas" (Partner Ledeger)
Agrega reportes de estado de resultado y balance

Installation
============

To install this module, you need to:

#. Install the module from Apps menu
#. The module will auto-install if l10n_ar and account_reports are installed

Configuration
=============

This module doesn't require specific configuration. It automatically:

#. Enhances the Partner Ledger report with CUIT information
#. Adds the "Cheques a fecha" menu under Accounting → Reporting → Legal Statements

Usage
=====

**Partner Ledger Report:**
#. Go to Accounting → Reporting → Partner Ledger
#. Generate the report normally - partner names will automatically include CUIT information

**Checks to Date Report:**
#. Go to Accounting → Reporting → Legal Statements → Cheques a fecha
#. Select the date up to which you want to see pending checks
#. Optionally filter by journal
#. Click "Confirmar" to generate the PDF report

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

Credits
=======

Images
------

* |company| |icon|

Contributors
============

* ADHOC SA

Maintainer
==========

|company_logo|

This module is maintained by ADHOC SA.

To contribute to this module, please visit https://www.adhoc.com.ar.
