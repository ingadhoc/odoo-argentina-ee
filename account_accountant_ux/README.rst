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
#. Responde "qué sucursales son la misma entidad fiscal" con el criterio propio definido en ``account_ux`` (``legal_entity_root_id``) en lugar del nativo, que toma el CUIT vacío como el del padre. De ahí cuelgan los reportes fiscales que ignoran el selector de compañías, el gate de los botones de export y las declaraciones.
#. Agrega el sufijo de compañía a las cuentas al expandir una línea de un reporte financiero con más de una compañía seleccionada (la otra mitad está en ``account_multicompany_ux``).
#. Agrega la opción de compañía "Bloquear conciliación entre diferentes compañías", que impide conciliar apuntes de compañías o sucursales distintas.
#. Sugiere, en los reportes que se presentan por CUIT (Libro de IVA y demás declaraciones), tildar las compañías de la misma entidad fiscal que quedaron afuera del selector. Nativamente esas compañías se descartan en silencio y el reporte sale parcial sin avisar. En los reportes que se filtran por el selector de compañías (Libro Mayor, Balance) no dice nada: ahí el usuario eligió las compañías a propósito.
#. El asiento de liquidación y de refundición no impone un modo: se sugiere seleccionar la entidad fiscal completa —un solo asiento, que se lee como la declaración— pero se puede liquidar compañía por compañía. Se acepta la selección cuando todas las compañías tildadas comparten entidad fiscal (nunca se mezclan CUIT) y una de ellas es ancestro de todas las demás, que es la que liquida y donde va el asiento. Dos hermanas sin su padre se rechazan con un mensaje de qué hacer: una cuenta que vive solo en una sucursal no la puede usar la otra. Antes se exigía "1 y solo 1 compañía" derivada de los diarios del reporte, que era otra pregunta y más débil: con todos los diarios en la padre, una selección de media entidad pasaba sin que nadie se enterara.
#. El botón de liquidación no queda deshabilitado por el gate nativo de sucursales ("seleccioná la compañía principal y todas sus sucursales"), que pedía algo distinto de lo que la liquidación necesita. El criterio se responde en un solo lugar y con el motivo concreto del rechazo.
#. Nombra la cuenta antes de que el asiento de liquidación falle: si una cuenta a netear pertenece solo a una sucursal, la compañía que liquida no la puede usar, así que se avisa cuál es y se sugiere liquidar esa sucursal por separado en lugar de dejar reventar el chequeo de consistencia de compañías.
#. Avisa en el wizard de liquidación si la compañía que liquida ya tiene un asiento de liquidación de ese reporte en el período. No bloquea: un segundo asiento puede ser una corrección.
#. Permite declarar un ejercicio fiscal explícito (``account.fiscal.year``) en la cabeza de una entidad fiscal, y no solamente en la compañía raíz como pide el nativo (*"You cannot have a fiscal year on a child company"*). La prohibición se mantiene para el resto de la entidad: el ejercicio se declara una sola vez, en su cabeza, y todas las compañías de la entidad lo leen de ahí. Es la otra mitad del ejercicio fiscal delegado a la entidad fiscal, cuya primera mitad —los campos ``fiscalyear_last_day`` / ``fiscalyear_last_month``— vive en ``account_ux``: sin esto, una sucursal que es cabeza de su propia entidad podría fijar los campos y seguir sin poder declarar un ejercicio irregular, porque el registro explícito le gana a los campos.
#. Resuelve ``compute_fiscalyear_dates`` en la cabeza de la entidad fiscal en lugar de en cada compañía por separado, para que toda la entidad responda lo mismo ante la misma fecha. Nativamente el registro de ejercicio se busca con ``company_id = self``, así que una sucursal nunca encuentra el que declaró su propia cabeza y contesta solo con los campos.

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
