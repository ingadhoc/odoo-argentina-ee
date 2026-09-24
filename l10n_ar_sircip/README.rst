.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-LGPL--3-blue.png
   :target: https://www.gnu.org/licenses/lgpl
   :alt: License: LGPL-3

===========================================
SIRCIP — Percepciones Convenio Multilateral
===========================================

.. warning::

   **Módulo exclusivo para Agentes de Percepción del SIRCIP.**

   Este módulo es solo para empresas que actúan como **Agentes de Percepción del SIRCIP**
   (Sistema de Recaudación del Control sobre Ingresos Brutos de Convenio Multilateral).
   No debe instalarse en empresas que no sean agentes de percepción de este régimen.

SIRCIP es el mecanismo de **ARCA** (ex AFIP) para la recaudación de percepciones de Ingresos
Brutos bajo el régimen de **Convenio Multilateral**. Es el equivalente al SIPRIB para empresas CM.

Instalación
===========

#. Instalar el módulo ``l10n_ar_account_tax_settlement`` (dependencia obligatoria).
#. Instalar este módulo ``l10n_ar_sircip``.
#. El ``post_init_hook`` crea automáticamente por empresa argentina:

   * Grupo de impuestos **SIRCIP**, con el código de tributo AFIP de percepción IIBB (``07``).
   * Cuenta **Percepción IIBB SIRCIP aplicada**, junto a las percepciones provinciales del plan de cuentas.
   * Impuestos plantilla, uno por tipo de registro de la DDJJ: ``Percepción SIRCIP`` (1),
     ``Percepción SIRCIP por no inscripto`` 2% (4) y ``Percepción SIRCIP por falta de alta`` 1% (5).
     Al facturar se crean copias por alícuota y por provincia de entrega.
   * Posición fiscal **Percepción - SIRCIP** (auto-detectable, secuencia 9999), para los clientes que
     no caen en ninguna otra posición fiscal.
   * La línea SIRCIP (percepción, ``Percepción SIRCIP por no inscripto``, archivo de padrón) en cada
     posición fiscal que ya tenga líneas de percepción: una factura toma una sola posición fiscal.
   * Diario de liquidación **Liquidación SIRCIP Aplicado**, con la etiqueta ``Perc IIBB SIRCIP Aplicada``.

Configuración
=============

Provincias adheridas
--------------------

El módulo se instala **sin provincias marcadas**. Cada jurisdicción informa desde cuándo implementa
SIRCIP y, hasta entonces, se siguen usando los regímenes actuales. A medida que eso ocurra, marcar
**Adherida a SIRCIP** (``l10n_ar_is_sircip``) en ``Contactos → Configuración → Provincias``.

**Fuente oficial de adhesiones:** `Spreadsheet de provincias SIRCIP <https://docs.google.com/spreadsheets/d/1yqf8C6ztxJZsmEQRC4-g2RttgMoJCqMi-Y-0_1mlugE/edit?gid=0#gid=0>`_

Posiciones fiscales provinciales
--------------------------------

Cuando una provincia pasa a SIRCIP, eliminar la línea de percepción de esa provincia en las posiciones
fiscales: desde ese momento la percepción se practica por SIRCIP. Las líneas de las provincias **no
adheridas** se mantienen: para un cliente con alta en una provincia no adherida (dígito 4 del campo 7),
esa línea calcula la percepción propia de la provincia y SIRCIP agrega la suya.

Uso
===

Carga del Padrón
----------------

#. Ir a ``Contabilidad → Configuración → AFIP → Padrón de Alícuotas por Compañía``.
#. Crear un nuevo registro con:

   * **Jurisdicción:** ``SIRCIP`` (la provincia ficticia creada por el módulo)
   * **Desde / Hasta:** el mes del padrón
   * **Archivo:** el TXT descargado del `Portal Federal Tributario — Descargas <https://www.ca.gob.ar/>`_

El padrón es mensual: sin padrón cargado para el mes no se pueden facturar ventas con la posición
fiscal SIRCIP.

**Formato del padrón (CSV separado por comas):**

.. code-block:: text

   periodo,cuit,razon_social_contri,jurisdiccion_sede,crc,alicuota_unica_letra,campo7
   202602,30100100106,MI EMPRESA SA,904,34,B,5225355222512555552512420

Tabla de alícuotas (letras A–X):

+-------+-------+-------+-------+-------+-------+
| A=0%  | E=0.2%| I=0.6%| M=1.2%| Q=1.8%| U=3.5%|
+-------+-------+-------+-------+-------+-------+
| B=0.01| F=0.3%| J=0.7%| N=1.4%| R=2%  | V=4%  |
+-------+-------+-------+-------+-------+-------+
| C=0.05| G=0.4%| K=0.8%| O=1.5%| S=2.5%| W=4.5%|
+-------+-------+-------+-------+-------+-------+
| D=0.1%| H=0.5%| L=1%  | P=1.6%| T=3%  | X=5%  |
+-------+-------+-------+-------+-------+-------+

Cálculo de percepciones en facturas
-----------------------------------

La percepción se calcula en cada factura con la **provincia de entrega** (dirección de entrega de la
factura o, si no tiene, la del cliente). El campo 7 del padrón se lee solo para esa provincia. Según la
planilla oficial *Aplicación Códigos* de la Comisión Arbitral:

+-------------------------------------+-------------------------------------------------------------+
| Caso                                | En la factura                                               |
+=====================================+=============================================================+
| Dígito 1, 3, 4 o 5                  | ``Percepción SIRCIP`` con la alícuota de la letra           |
+-------------------------------------+-------------------------------------------------------------+
| Dígito 2 (adherida, sin alta)       | ``Percepción SIRCIP`` y, en otra línea,                     |
|                                     | ``Percepción SIRCIP por falta de alta en (provincia)`` 1%   |
+-------------------------------------+-------------------------------------------------------------+
| Letra A (0%)                        | Nada (con dígito 2, solo la sobretasa). Se declara como     |
|                                     | informativo en la DDJJ                                      |
+-------------------------------------+-------------------------------------------------------------+
| Fuera del padrón, entrega adherida  | ``Percepción SIRCIP por no inscripto`` 2%                   |
+-------------------------------------+-------------------------------------------------------------+
| Fuera del padrón, entrega no        | Nada                                                        |
| adherida                            |                                                             |
+-------------------------------------+-------------------------------------------------------------+

El dígito 3 (adherida, sin alta y **sin** sobrealícuota) no es el tipo de registro 3 *Excluido* de la
DDJJ: los excluidos llegan por los *ajustes al padrón* (ver Pendientes). Con dígito 4, la percepción
propia de la provincia no adherida la calcula su línea de posición fiscal.

El padrón se consulta una vez por cliente y por mes, y queda en la pestaña **Contabilidad** del
contacto (``l10n_ar.partner.tax``). El campo **Referencia** guarda lo que usa la DDJJ:
``SIRCIP | crc:XX | letra:F | campo7:YYYYY...`` (o ``SIRCIP | no inscripto``).

Generación del TXT de DDJJ
--------------------------

#. Ir al diario **Liquidación SIRCIP Aplicado**.
#. Seleccionar las percepciones del período a liquidar.
#. Usar la acción **Descargar TXT** para generar el archivo ``SIRCIP_DDJJ.txt``.
#. Importar en el menú *Declaración Jurada* del `Portal Federal Tributario — DDJJ <https://www.ca.gob.ar/sistemas/sircip>`_.

Registros que genera (campo 5, *tipo de registro*):

* **1 Percepción**, **4 No inscripto** y **5 Sobretasa**: uno por percepción, según el impuesto.
* **6 Anulada**: las notas de crédito, con el número y el CRC de la factura original. Una nota de crédito
  sin factura original frena la generación, porque el portal la rechaza.
* **2 Informativo**: las facturas de los meses liquidados a clientes con letra A y entrega en provincia
  adherida. No llevan percepción: salen de cruzar las facturas del mes.

Campos fijos: régimen (4) siempre ``1`` (Régimen General), ABM (17) siempre ``A``, jurisdicción (7) la de
entrega y monto (14) igual a base × alícuota / 100 redondeado a 2 decimales, que es como lo valida el
portal. Formato completo: ``doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf``.

Referencias Oficiales
=====================

Los documentos de referencia se encuentran en la carpeta ``doc/sircip/``:

* `Diseño de Registros SIRCIP (PDF oficial) <https://www.ca.gob.ar/descargas/sircip/registros/Diseno_de_Registros_del_Sistema_SIRCIP.pdf>`_
* `Provincias adheridas al SIRCIP <https://docs.google.com/spreadsheets/d/1yqf8C6ztxJZsmEQRC4-g2RttgMoJCqMi-Y-0_1mlugE/edit?gid=0#gid=0>`_
* `Matriz de Aplicación de Códigos (Campo 7) <https://docs.google.com/spreadsheets/d/1MXUlg43Ng-xBIx7xO5epLf21qJCEX7oFWpCzZ2b8PIk/edit?gid=664128533#gid=664128533>`_
* `Recopilación Q&A CESSI <https://docs.google.com/document/d/1Apl-WG06AZZHXB70uVAWbzcg3sw1ncshoaBVcTdw8AE/edit?tab=t.0>`_
* `Portal Federal Tributario SIRCIP <https://www.ca.gob.ar/sistemas/sircip>`_

Pendientes
==========

**Excluidos (tipo de registro 3) — ajustes al padrón**
  La Comisión Arbitral publica durante el mes un archivo de *ajustes al padrón* (mismo diseño que el
  padrón) con contribuyentes excluidos: no se percibe y se declara con tipo 3. Todavía no se procesa.

**Una sola entrega por factura**
  Si una factura tiene artículos entregados en distintas jurisdicciones, la Comisión Arbitral indica
  tratar cada entrega como una factura separada. Se toma una sola provincia de entrega por factura.

**TXT de DDJJ — validación contra el portal**
  Pendiente validar un período completo contra el portal SIRCIP con archivos reales.

**Soporte de archivos comprimidos (ZIP/RAR) en la carga del padrón**
  Solo se acepta el TXT plano. Implementar en ``_get_sircip_aliquot()`` siguiendo el patrón de
  ``_read_parp_from_binary()`` para Santa Fe si el portal lo empieza a publicar comprimido.

**Posiciones en el campo 7 por jurisdicción**
  El mapa ``SIRCIP_CAMPO7_POSITION`` en ``models/account_fiscal_position_l10n_ar_tax.py`` sale del PDF y
  de los ejemplos del padrón. Si ARCA cambia el orden de las jurisdicciones, hay que actualizarlo.

Créditos
========

Imágenes
--------

* |company| |icon|

Autores
-------

* |company|

Maintainer
----------

|company_logo|
