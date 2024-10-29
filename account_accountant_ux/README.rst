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

#. Mueve el menu "Caja y bancos" a nuevo menú de Accounting
#. Agrega el parámetro "Compañía" en el wizard de Fechas Bloqueadas.
#. Agrega una opción en las configuraciones de contabilidad para forzar moneda de la compañía en los informes de seguimiento.
#. Agrega filtros de "Igual Monto", "Monto Aproximado" y "Monto Menor" en el asistente de conciliación.
#. Determina por defecto el filtro "Igual Monto" en el asistente de conciliación.
#. Para asientos contables, el botón "Pagos" te lleva efectivamente al pago, mejorando la compatibilidad con asientos migrados de versiones anteriores.
#. Ajustar conciliación bancaria para compatibilidad con la opción de reconciliar en la moneda de la compañía.
#. restaurar comportamiento de 16 donde el boton 'libro mayor' de partners llevaba al informe (Ahora lleva a tree sin este cambio).
#. desde el informe partner ledger, al ir a los journal items, vamos a la vista de apuntes que usamos para los menus "customer/supplier ledger" para unificar comportamiento (nativamente odoo manda a una _tree_grouped_partner)

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
