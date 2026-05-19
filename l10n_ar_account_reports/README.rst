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

**Partner Ledger Report Enhancement**

Modifies the native Partner Ledger (Libro Mayor de Empresas) report to include Argentine fiscal information alongside each partner's name. The standard Odoo report only shows "Partner Name", while with this module it displays "Partner Name (CUIT: 1234567890)".

This functionality is essential for fiscal compliance in Argentina, as the report serves as the official detail of Debtors and Creditors at year-end, required for Annual Balance presentation to accounting and tax authorities.

**Interface changes:**
- Adds a new "Cheques a fecha" menu under Accounting → Reporting → Legal Statements
- Includes a wizard with fields to select limit date and journal (optional)
- Generates a PDF report with detailed listing of pending checks
- Archivos para declaración de distintos impuestos (principalmente percepciones y retenciones)

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

* SANTA FE: especificación en /doc/Santa Fe (siprib). La especificación se obtuvo de https://www.santafe.gov.ar/index.php/web/content/view/full/249467/%28subtema%29/102284 --> aplicativo SiPRIB (versión 4.0 Release 2) de SIAP.

* TUCUMAN: especificación en doc/Tucuman/MRETPER6R2.pdf a partir de la página 12

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
