.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-LGPL--3-blue.png
   :target: https://www.gnu.org/licenses/lgpl
   :alt: License: LGPL-3

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

Antes de importar, tienen que existir los impuestos que el importador busca. Todos
deben ser del tipo de uso del diario (compras o ventas) y no estar incluidos en el
precio:

#. Para comprobantes con importe en "Otros Tributos": un impuesto del grupo con
   código de tributo ARCA ``99`` (Otros Impuestos).
#. Si la compañía es Responsable Inscripto: el IVA de cada alícuota usada en el
   listado y, según el caso, IVA Exento, IVA No Gravado e IVA No Corresponde.

Si falta alguno, la importación se detiene y nombra el impuesto que no encontró.


Argentinian Importing Bills from ARCA
=====================================
Importa facturas de compra y de venta a partir de los listados "Mis Comprobantes"
que exporta ARCA en formato Excel (.xlsx): los "Comprobantes Recibidos" sobre un
diario de compras y los "Comprobantes Emitidos" sobre un diario de ventas.

El importador se activa al soltar el archivo sobre un diario cuando se cumplen
todas estas condiciones:

* El diario es de compras, o de ventas sin punto de venta de ARCA.
* La compañía es argentina y es Responsable Inscripto, IVA Sujeto Exento o
  Monotributo.
* Todos los archivos soltados son planillas (.xlsx, .xls, .ods o .csv). Si alguno
  no lo es, sigue el flujo estándar de Odoo para crear facturas desde adjuntos.

El módulo lee la planilla, arma una previsualización con una línea por
comprobante y recién al confirmar crea los asientos. Qué hace con cada línea:

* **Reconoce los comprobantes ya importados.** Busca el contacto del listado y
  una factura suya con el mismo número; las que ya existen quedan resaltadas en
  amarillo y no se vuelven a crear.

* **Resuelve el contacto por su documento.** El CUIT va al campo de identificación
  fiscal y el resto de los documentos (DNI, CUIL, pasaporte) a los identificadores
  adicionales del contacto. Si no existe, lo crea con el nombre y el documento que
  trae el listado. El número se guarda como lo guarda Odoo, sin puntos ni guiones, así
  que el mismo contacto se reconoce entre una importación y la siguiente. Un número que
  no es un documento válido de ese tipo no corta la importación: va al campo de
  identificación fiscal tal cual vino, para corregirlo después en el contacto.
  Cuando el listado no trae documento, el contacto se busca por nombre entre los que
  no tienen ninguno, sin distinguir mayúsculas. Si tampoco trae nombre, la
  importación se detiene y nombra el comprobante: sin ninguno de los dos no hay
  forma de saber de quién es.

* **Discrimina el IVA por alícuota.** Arma una línea por cada alícuota con importe
  (0%, 2,5%, 5%, 10,5%, 21% y 27%) y líneas separadas para los importes exentos y
  no gravados. Si no queda ninguna, carga una línea única con IVA No Corresponde.
  Si la compañía no es Responsable Inscripto, el comprobante se carga en una línea
  sin impuestos por el total menos los otros tributos.

* **Agrega otros tributos.** Los importes de la columna "Otros Tributos" se cargan
  con el asistente de impuestos de la factura (``account_invoice_tax``).

* **Respeta la moneda del comprobante**, con el tipo de cambio del listado.

* **Valida opcionalmente.** Con "Auto-validate Imported Invoices" confirma las
  facturas cuyo total coincide con el del listado (tolerancia de 0,10). El resto
  queda en borrador.

Importación desde la guía de importación inicial
------------------------------------------------
El mismo importador aparece en la guía de importación inicial de contabilidad
(``account_balance_import``), con dos accesos: "Import Sales from ARCA" e
"Import Purchases from ARCA". Para usarlos, la compañía tiene que tener definidos
los periodos fiscales. En ese camino se pide una cuenta de contrapartida, que
reemplaza a las cuentas de las líneas del asiento (salvo la de cuenta a cobrar o a
pagar), y solo se admiten comprobantes anteriores a la fecha de inicio de la
contabilidad de la compañía.

Detalles técnicos
-----------------
* ``account.journal``: ``create_document_from_attachment`` decide si el archivo va
  al importador; ``import_bills_from_xls`` lee la planilla con pandas y openpyxl,
  valida las columnas y crea el asistente. En compras toma las columnas del
  emisor y en ventas las del receptor; el número se arma como ``PPPPP-NNNNNNNN``.
* ``account.import.summary``: ``action_import_sales_from_arca`` y
  ``action_import_purchases_from_arca`` abren el asistente desde la guía; los
  botones los agrega un patch de ``AccountImportGuide`` en ``static/src/``.
* ``afip.import.wizard`` (transitorio): cabecera de la importación.
  ``action_process_file`` procesa el archivo subido desde la guía y
  ``action_confirm`` crea las facturas.
* ``afip.import.wizard.line`` (transitorio): una línea por comprobante, con el
  campo almacenado ``exists`` y la resolución de contacto, tipo de documento
  (``l10n_latam.document.type`` por código), moneda (``$`` es ARS) y tipo de
  factura (según el ``internal_type`` del documento).
* Permisos: grupo ``account.group_account_invoice``.
* Requiere las librerías de Python ``pandas`` y ``openpyxl``.


Usage
=====

Desde el diario:

#. Descargue de ARCA, en "Mis Comprobantes", los Comprobantes Recibidos o
   Emitidos del período en Excel.
#. Vaya a Contabilidad > Tablero y arrastre el archivo sobre el diario de compras
   o de ventas que corresponda.
#. Revise la previsualización: las líneas en amarillo ya existen y no se crean.
   Con el ícono de borrar puede quitar una línea.
#. Marque "Auto-validate Imported Invoices" si quiere que las facturas queden
   confirmadas, y presione "Create Invoices".

Desde la guía de importación inicial:

#. Defina los periodos fiscales de la compañía.
#. En la guía, elija "Import Sales from ARCA" o "Import Purchases from ARCA".
#. Elija el diario y la cuenta de contrapartida, cargue el archivo y presione
   "Continue".
#. Revise la previsualización y presione "Create Invoices".

El listado tiene que ser el que exporta ARCA, sin cambios manuales: si faltan
columnas el importador las nombra y no importa nada.


Bug Tracker
===========


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
