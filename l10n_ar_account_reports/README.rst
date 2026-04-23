.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

==========================================
Customized Accounting Reports - Argentina
==========================================

Customizes Odoo standard accounting reports to meet specific Argentine requirements, including Income Statement and Balance Sheet according to Argentine regulations, automatic configuration of account tags, Partner Ledger enhancements, and tax declaration file generation for various provincial tax authorities.

Functional description
======================

**1. Income Statement and Balance Sheet Reports**

Provides Income Statement (Estado de Resultados) and Balance Sheet (Estado Patrimonial) structured according to Argentine accounting regulations, with proper classification of accounts.

**2. Automatic Account Tags Configuration**

When installing the Argentine chart of accounts, the module automatically assigns the corresponding account tags to each account based on its code and type, enabling proper report generation.

**3. Partner Ledger Report Enhancement**

Modifies the native Partner Ledger (Libro Mayor de Empresas) report to include Argentine fiscal information alongside each partner's name. The standard Odoo report only shows "Partner Name", while with this module it displays "Partner Name (CUIT: 1234567890)".

This functionality is essential for fiscal compliance in Argentina, as the report serves as the official detail of Debtors and Creditors at year-end, required for Annual Balance presentation to accounting and tax authorities.

**4. Tax Declaration Files (Percepciones y Retenciones)**

Generates text files for tax declaration to various provincial tax authorities (mainly withholdings and perceptions):

**Inflation adjustment index management**

Provides a model to manage inflation adjustment indices, which are used to adjust amounts for inflation. The model ensures that only one index can be set per month and that the date of the index corresponds to the first day of the month. The indexes are updated automatically from https://www.facpce.org.ar/indices-facpce/ .

Archivos para declaración de impuestos
======================================

* ARBA (PBA):
   * https://web.arba.gov.ar/agentes#presentacion-de-ddjj --> hacer click en "Instructivos y Marco Normativo - NOVEDAD -" dentro de DDJJ Periódicas Web IIBB
   * TXT Webservice (A122R): https://web.arba.gov.ar/Instructivos-y-Marco-Normativo-A-122R (ese enlace se obtiene de https://web.arba.gov.ar/agentes#presentacion-de-ddjj , luego hay que ir a la sección "Comprobantes de Retención (A-122R) Nuevo" y hacer click en "Instructivo y Marco Normativo"). Vigente desde 01/03/2026.

* AGIP:  https://www.agip.gob.ar/agentes/agentes-de-recaudacion/ib-agentes-recaudacion/aplicativo-arciba/aclaraciones-sobre-las-adecuaciones-al-aplicativo-e-arciba- (Version 3.0 aplicada el 07-05-2024)
   * Notas de credito  https://www.agip.gob.ar/filemanager/source/Agentes/De%20Recaudacion/Ingresos%20brutos/NC.PDF
   * Retencion y percepciones  https://www.agip.gob.ar/filemanager/source/Agentes/De%20Recaudacion/Ingresos%20brutos/RP.PDF

* MENDOZA https://www.atm.mendoza.gov.ar/portalatm/ModificarParametros?tipo=descargarUrl&url=/zoneBottom/serviciosDescargas/sarepe/files/SAREPE.pdf

* MISIONES: https://atmisiones.gob.ar/agentes-de-retencion-y-percepcion/ (ingresar en "https://atmisiones.gob.ar/", abajo a la derecha hacer click en "Guías y Manuales de Usuario" luego en "Manuales de Usuarios" finalmente en "Agentes Ret/Percep") --> hacer click en "AG IIBB -Instructivo del Formato Archivo carga DDJJ Retenciones desde 01-06-2023" y "AG IIBB -Instructivo del Formato Archivo carga DDJJ Percepción desde 01-06-2023".
            Correo DGR: mesadeayuda@tsgroup.com.ar

* SIRCAR: especificación en /doc/sircar

* SIFERE: especificación en /doc/sifere

* SANTA FE: especificación en /doc/Santa Fe (siprib)

* TUCUMAN: especificación en doc/Tucuman/MRETPER6R2.pdf a partir de la página 12

**5. VAT Withholdings and Perceptions Report (IVA Sufrido)**

Generates reports for VAT withholdings and perceptions suffered, used for tax compliance and declaration purposes.

Installation
============

To install this module:

#. The module will auto-install if l10n_ar, account_reports and l10n_ar_reports are installed
#. It can also be installed manually from the Apps menu

Configuration
=============

This module doesn't require specific configuration. It automatically:

#. Creates the Income Statement and Balance Sheet reports for Argentina
#. Configures account tags when installing the Argentine chart of accounts
#. Enhances the Partner Ledger report with CUIT information
#. Provides access to tax declaration file generators

Usage
=====

**Income Statement and Balance Sheet:**
#. Go to Accounting → Reporting → Income Statement (or Balance Sheet)
#. Select the desired period
#. The report is generated with the structure according to Argentine regulations

**Partner Ledger:**
#. Go to Accounting → Reporting → Partner Ledger
#. Generate the report normally - partner names will automatically include CUIT information

**Tax Declaration Files:**
#. Go to Accounting → Reporting → Argentina
#. Select the appropriate report (ARBA, AGIP, SIFERE, SIRCAR, etc.)
#. Configure the period and filters
#. Generate and download the text file for tax authority submission

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
