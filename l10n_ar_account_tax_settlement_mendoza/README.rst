.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

======================
Tax settlement Mendoza
======================

Este módulo imlementa:

* Cálculo de impuestos para retenciones de mendoza.

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

* En 'Contabilidad / Configuración / Ajustes' en sección "Localización para Argentina" el usuario debe subir todas las semanas el archivo csv de riesgo fiscal en la sección de riesgo fiscal. Lo debe hacer para cada una de las compañías.
* El impuesto 'Retención IIBB Mendoza Aplicada' debe tener código de régimen (campo 'Código AFIP' l10n_ar_code)

Usage
=====

* Subir semanalmente el archivo csv de riesgo fiscal provisto por la provincia de Mendoza en 'Contabilidad / Configuración / Ajustes' en sección "Localización para Argentina" en la sección de riesgo fiscal.
* Subir el archivo csv de actividades AFIP en el modelo afip.activity.
* La posición fiscal "Retenciones" creada por upgrade line 1415 [RET18] Migración retenciones de  Ganancias debe tener el impuesto "Ret IIBB MZA 0%" en la pestaña de Percepciones y Retenciones con código python. Esto se hace en odoo-argentina-ee/l10n_ar_account_tax_settlement_mendoza/hooks.py .
* Cuando se hace una factura de proveedor que tiene activities_mendoza_ids asociadas, y luego se realiza el pago correspondiente de dicha factura, el sistema automáticamente aplicará la retención de IIBB Mendoza según el riesgo fiscal del proveedor y la alícuota de la actividad en el modelo afip.activity.

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
