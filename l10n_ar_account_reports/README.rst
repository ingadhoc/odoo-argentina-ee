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

<<<<<<< 802c97bdef05a989ed2f90a29c45366dd77d927d
Customizes Odoo standard accounting reports to meet specific Argentine requirements, adding necessary fiscal information for balance presentation and generating additional reports for check control.

Functional description
======================

This module adds two main functionalities:

**1. Partner Ledger Report Enhancement**

Modifies the native Partner Ledger (Libro Mayor de Empresas) report to include Argentine fiscal information alongside each partner's name. The standard Odoo report only shows "Partner Name", while with this module it displays "Partner Name (CUIT: 1234567890)".

This functionality is essential for fiscal compliance in Argentina, as the report serves as the official detail of Debtors and Creditors at year-end, required for Annual Balance presentation to accounting and tax authorities.

**2. Checks to Date Report**

Adds a new functionality that allows generating reports of pending checks up to a specific date, differentiating between:
- Own checks (issued by the company) that have not yet been debited
- Third-party checks (received) that are in portfolio

This report is fundamental for cash flow control and bank reconciliation, allowing to know the real status of checks at the end of accounting periods.

**Interface changes:**
- Adds a new "Cheques a fecha" menu under Accounting → Reporting → Legal Statements
- Includes a wizard with fields to select limit date and journal (optional)
- Generates a PDF report with detailed listing of pending checks
||||||| b2ba4cfcc8e9d34b5977c4b88f001995a7e2d083
Agrega el CUIT de cada partner en el reporte "Libro Mayor de Empresas" (Partner Ledeger)
Este módulo también permite obtener un reporte de cheques a fecha, tanto propios como de terceros.
=======
Agrega el CUIT de cada partner en el reporte "Libro Mayor de Empresas" (Partner Ledeger)
Agrega reportes de estado de resultado y balance
>>>>>>> b0c67ff5908160b7c8fe0be33af0217abde5aea9

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
