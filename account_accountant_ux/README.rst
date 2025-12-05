.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

=====================
Account Accountant UX
=====================

#. Agrega el parámetro "Compañía" en el wizard de Fechas Bloqueadas.
#. Agrega filtros de "Igual Monto", "Monto Aproximado" y "Monto Menor" en el asistente de conciliación.
#. Determina por defecto el filtro "Igual Monto" en el asistente de conciliación.
#. Ajustar conciliación bancaria para compatibilidad con la opción de reconciliar en la moneda de la compañía.
#. Agrega advertencia para posibles conciliaciones cruzadas entre partners.
#. Desde el informe partner ledger, al ir a los journal items, vamos a la vista de apuntes que usamos para los menus "customer/supplier ledger" para unificar comportamiento (nativamente odoo manda a una _tree_grouped_partner)
#. Agrega una estrategia de autoconciliacion que Permite reconciliar todas las lineas de un partner en un solo conciliacion parcial o total
#. Modifica el botón "Due" de los partners para que sea siempre visible y modifica su nombre a "Libro Mayor de Empresa".
#. Agrega campo booleano "Requerir Filtro Custom" en la configuración de reportes. Si está activo y no hay filtros de partners o filtros personalizados aplicados, el reporte no cargará datos y mostrará un mensaje de advertencia.
#. Los reportes contables de partner (Partner Ledger, Aged Receivable, Aged payable) vienen configurados por defecto con el campo "Requerir Filtro Custom" activo (True), forzando al usuario a aplicar filtros antes de cargar los datos.

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

#. Nothing to configure

Usage
=====

To use this module, you need to:

#. Go to ...

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
