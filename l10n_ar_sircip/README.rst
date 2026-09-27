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
#. Instalar no configura ninguna compañía: cada agente se activa desde Ajustes (ver Configuración). Solo con
   datos de demostración la compañía RI demo queda como agente, con un padrón del mes.
#. Al activar una compañía como agente, el módulo le crea:

   * Grupo de impuestos **SIRCIP**, con el código de tributo AFIP de percepción IIBB (``07``).
   * Cuenta **Percepción IIBB SIRCIP aplicada**, junto a las percepciones provinciales del plan de cuentas. Si
     el plan no trae esa cuenta (monotributo, planes personalizados), se elige en Ajustes.
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

Compañías agentes de percepción
-------------------------------

Para cada compañía que sea agente de percepción SIRCIP:

#. En ``Contabilidad → Configuración → Ajustes → Localización argentina``, marcar **Agente de percepción
   SIRCIP**. Si el plan de cuentas no trae la cuenta de percepciones IIBB aplicadas, elegir la **Cuenta de
   percepción SIRCIP**; si no, se crea sola. Guardar.
#. Marcar las provincias adheridas (ver abajo).
#. Cargar el padrón del mes (ver *Carga del Padrón*).
#. Revisar las posiciones fiscales: el formulario avisa si a alguna le falta la línea SIRCIP o tiene percepciones
   de provincias adheridas.

En las compañías agentes, toda posición fiscal con percepciones que se crea o se edita después recibe sola la
línea SIRCIP; guardar de nuevo los Ajustes tampoco duplica nada. La línea SIRCIP, y toda línea de la posición fiscal **Percepción - SIRCIP**, solo
puede ser una percepción que lee el archivo de padrón.

Provincias adheridas
--------------------

El módulo se instala **sin provincias marcadas**. La entrada en vigencia de SIRCIP es el **01/12/2026**
(Disposición de Presidencia 7/2026 de la Comisión Arbitral), con las jurisdicciones que se detallen en una
disposición posterior. Cada jurisdicción informa desde cuándo implementa SIRCIP y, hasta entonces, se siguen
usando los regímenes actuales. A medida que eso ocurra, marcar
**Adherida a SIRCIP** (``l10n_ar_is_sircip``) en ``Contactos → Configuración → Provincias``.

**Fuente oficial de adhesiones:** `Spreadsheet de provincias SIRCIP <https://docs.google.com/spreadsheets/d/1yqf8C6ztxJZsmEQRC4-g2RttgMoJCqMi-Y-0_1mlugE/edit?gid=0#gid=0>`_

Posiciones fiscales provinciales
--------------------------------

Cuando una provincia pasa a SIRCIP, eliminar la línea de percepción de esa provincia en las posiciones
fiscales (el formulario de la posición fiscal lo avisa): desde ese momento la percepción se practica por SIRCIP. Las líneas de las provincias **no
adheridas** se mantienen: para un cliente con alta en una provincia no adherida (dígito 4 del campo 7),
esa línea calcula la percepción propia de la provincia y SIRCIP agrega la suya.

Cada provincia no adherida con percepción va en **su propia posición fiscal** (provincia de entrega, detección
automática y la responsabilidad AFIP del cliente), no en **Percepción - SIRCIP**: las líneas de una posición
fiscal se aplican a toda factura que la use, cualquiera sea la entrega. **Percepción - SIRCIP** tiene secuencia
9999 y no tiene provincias, así que cualquier posición fiscal de la provincia de entrega le gana.

Si un cliente tiene dígito 4 en la provincia de entrega y la posición fiscal de la factura o del pedido no
tiene percepción de esa provincia, Odoo **no deja validar la factura ni confirmar el pedido**: la alícuota
provincial no la puede adivinar. El botón *Buscar/Crear posición fiscal* abre la posición fiscal de esa
provincia si existe, con el motivo por el que no se aplicó (sin detección automática, sin la provincia, sin la
responsabilidad del cliente o con una posición fiscal fija en el contacto), o una nueva ya armada con la
percepción de la provincia (cálculo manual) y la línea SIRCIP, para ajustar la alícuota o el webservice.
También frena si la línea de la provincia es manual (sin webservice), su impuesto por defecto es 0% y el
contacto no tiene alícuota cargada para esa provincia y período: el botón *Abrir contacto* lleva a cargarla.
Vale para cualquier provincia de entrega, no solo para las del ejemplo.

Uso
===

Carga del Padrón
----------------

#. Ir a ``Contabilidad → Configuración → AFIP → Padrón de Alícuotas por Compañía``.
#. Crear un nuevo registro con:

   * **Jurisdicción:** ``SIRCIP`` (la provincia ficticia creada por el módulo; solo se ofrece acá y en los
     impuestos, no en los contactos)
   * **Desde / Hasta:** el mes del padrón
   * **Archivo:** el TXT descargado del `Portal Federal Tributario — Descargas <https://www.ca.gob.ar/>`_, suelto o
     comprimido en ZIP (con un solo archivo adentro). RAR no se acepta: descomprimirlo antes.

El padrón es mensual: sin padrón cargado para el mes no se pueden facturar ventas con la posición
fiscal SIRCIP. El período del archivo (primera columna) tiene que ser el mes de **Desde**: la Comisión Arbitral
publica el del mes siguiente el día 22, y cargarlo en el mes equivocado da error.

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

La percepción se calcula en cada factura y en cada pedido de venta con la **provincia de entrega** (dirección
de entrega del comprobante o, si no tiene, la del cliente). En los pedidos la calcula ``l10n_ar_sale``, que
pasa la entrega en el contexto ``l10n_ar_delivery_partner_id``. El campo 7 del padrón se lee solo para esa provincia. Según la
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
#. Usar la acción **Descargar TXT** para generar el archivo ``SIRCIP_DDJJ.txt``. En el diario, el tipo de
   liquidación es **TXT DDJJ SIRCIP (módulo SIRCIP)**.
#. Importar en el menú *Declaración Jurada* del `Portal Federal Tributario — DDJJ <https://www.ca.gob.ar/sistemas/sircip>`_.

.. note::

   Hay otra implementación del TXT de SIRCIP en ``l10n_ar_account_tax_settlement``
   (`PR #896 <https://github.com/ingadhoc/odoo-argentina-ee/pull/896>`_, sin mezclar), que en el diario aparece
   como **TXT Percepciones Aplicadas SIRCIP** y genera ``Percepciones_sircip.txt``. Se va a unificar en una sola
   (ver Pendientes); mientras tanto, la de este módulo es la que usa el tipo de registro, el CRC y la provincia
   de entrega.

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
* `Guía Operativa SIRCIP <https://drive.google.com/file/d/1AOYTXom1U-lmyJSqSCxfyHxHUWASUX-x/view>`_
* `Portal Federal Tributario SIRCIP <https://www.ca.gob.ar/sistemas/sircip>`_

Pendientes
==========

Se tachan (``[x]``) a medida que se resuelven. La numeración es la de la actividad de la tarea.

**TXT de DDJJ** (según el diseño de registros vigente y la Guía Operativa de la Comisión Arbitral; lo trabaja
la subtarea de la DDJJ, que además decide cómo unificar las dos implementaciones del TXT):

- ``[ ]`` 1. NC: mismo tipo de registro que la percepción original (1, 4 o 5), comprobante 102, campos 12 y 14
  negativos, campo 15 con tipo + letra + punto de venta + número (``001A0002311312221``), campo 16 vacío y CRC
  de la percepción original. Hoy: tipo 6, importes positivos, ``00002-03431222`` y campo 16 lleno.
- ``[ ]`` 2. Campo 6 en ``0``. Hoy: vacío.
- ``[ ]`` 3. Campos 10 y 11 como el ejemplo oficial (``2``, ``3431222``). Hoy: con ceros a la izquierda.
- ``[ ]`` 4. Campo 8 con todos los tipos de comprobante oficiales. Hoy: solo 1, 2 y 102.
- ``[ ]`` 5. Informativo (tipo 2) para cualquier jurisdicción de entrega. Hoy: solo si es adherida.
- ``[ ]`` 6. Presentación en ZIP, con la cantidad de registros y el monto total a la vista. Hoy: TXT suelto.

**Normativa y padrón:**

- ``[x]`` 7. Vigencia al 01/12/2026 (Disposición de Presidencia 7/2026).
- ``[x]`` 8. Padrón de devoluciones: son las devoluciones que aprueba el Comité SURA después del vencimiento de la DDJJ
  (RG 9/2025, Anexo I, B.4). No aplica por ahora: el campo 16 de la DDJJ no se usa hasta que la Comisión Arbitral
  lo habilite.
- ``[x]`` 9. El período del archivo del padrón tiene que ser el mes del padrón (se publica el día 22 del mes anterior).

**Configuración y cálculo:**

- ``[x]`` 10. Compañías creadas después de instalar: se configuran desde Ajustes (*Agente de percepción SIRCIP*).
- ``[x]`` 11. Posiciones fiscales creadas o editadas después: reciben sola la línea SIRCIP, y el formulario avisa si
  tienen percepciones de provincias adheridas. Con dígito 4 y sin percepción de la provincia de entrega, no se
  puede validar la factura ni confirmar el pedido.
- ``[x]`` 12. La línea SIRCIP, y toda línea de la posición fiscal SIRCIP, solo puede ser percepción + archivo de padrón.
- ``[x]`` 13. La provincia ficticia SIRCIP no se ofrece en los contactos ni se les puede asignar.
- ``[x]`` 14. Pedidos de venta con la dirección de entrega del pedido.
- ``[x]`` 15. Cuenta SIRCIP en planes sin la cuenta de percepciones IIBB aplicadas (monotributo,
  personalizados): se elige en Ajustes, y guardar sin ella da un error claro.
- ``[x]`` 16. Excluidos (tipo 3). No aplica por ahora: el campo 6 (código de operación exceptuada) solo admite
  ``0 - Inexistente`` en el diseño vigente, y los *ajustes al padrón* no figuran en la documentación oficial.
- ``[ ]`` 17. Varias entregas por factura y la leyenda del no inscripto por jurisdicción. La normativa no lo trata;
  según el Q&A CESSI va una factura por entrega. Hoy: una sola provincia de entrega por factura.
- ``[x]`` 18. Padrón comprimido en ZIP. RAR no: necesita una librería y el binario ``unrar`` en el servidor.
- ``[ ]`` 19. Validar un período completo contra el portal SIRCIP.
- ``[x]`` 20. CUITs del padrón demo ficticios y comentarios del módulo en inglés y mínimos.
- ``[ ]`` 21. Forward-port a 19.

**Posiciones en el campo 7 por jurisdicción**
  El mapa ``SIRCIP_CAMPO7_POSITION`` en ``models/account_fiscal_position_l10n_ar_tax.py`` sale del PDF y de los
  ejemplos del padrón. Si ARCA cambia el orden de las jurisdicciones, hay que actualizarlo.

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
