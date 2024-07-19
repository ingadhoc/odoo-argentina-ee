.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

========================
Tax Settlements For Sire
========================

Implementación:

* Archivos para declaración de impuesto sire de retenciones aplicadas a sujetos domiciliados en el exterior.

Archivos para declaración de impuestos
======================================

* SIRE: https://www.afip.gob.ar/sire/documentos/SIRE-especificacion-para-emision-por-lote.pdf apartado 3. F2003 CERTIFICADOS SUJETOS DOMICILIADOS EN EL EXTERIOR.
* CERTIFICADOS DE RETENCIÓN IMPOSITIVA: https://www.afip.gob.ar/sire/documentos/SIRE-especificacion-para-emision-por-lote.pdf apartado 5. F2005 CERTIFICADOS DE RETENCIÓN IMPOSITIVA (beta: nunca fue testeado).

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

   1. Crear diario de liquidación con la etiqueta para liquidación "Sire" y elegir "TXT Retenciones SIRE" en el campo "Impuesto de liquidación".
   2. Crear impuesto de sire y agregar la etiqueta "Sire" en cuadrículas de impuesto en vista formulario del impuesto y agregar codigo de regimen en el campo "Codigo de regimen IVA" en la solapa "Opciones avanzadas" del impuesto.
   3. El contacto debe tener país y si es tipo 'individual' entonces tendrá que establecer el país de nacimiento y la fecha de nacimiento en la solapa "Datos Fiscales" de la vista formulario del contacto.
   4. Establecer "Sire Codigo Alicuota" en la solapa "Datos Fiscales" de la vista formulario del contacto. Si no lo establece entonces en el pago será requerido que lo establezca.

Usage
=====

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

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
